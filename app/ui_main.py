import os
import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QFileDialog, QListWidget, QListWidgetItem,
    QMessageBox, QComboBox, QGroupBox, QFormLayout
)

from .config_store import load_config, save_config
from .run_io import create_run_dir, save_json, append_text, copy_input_images
from .utils import file_to_data_url
from .dashscope_client import call_sync, extract_image_urls, download_images


class MainWindow(QMainWindow):
    """
    傻瓜版：
    - 固定 region=cn-beijing
    - 固定 enable_interleave=false（图像编辑）
    - 固定 n=1
    - 固定 DataInspection disable
    - 图片输入固定 Base64 data URL（无需 OSS、公网链接）
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wan2.6 图片生成与编辑")

        self.cfg = load_config()
        self.selected_images: list[str] = []

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        # ====== 1) API Key 区 ======
        g_key = QGroupBox("第 1 步：粘贴 API Key（只需要一次）")
        f_key = QFormLayout(g_key)

        self.ed_api = QLineEdit()
        self.ed_api.setEchoMode(QLineEdit.Password)

        saved_key = (self.cfg.get("api_key", "") or "").strip()
        self.ed_api.setText(saved_key)

        btn_toggle = QPushButton("显示/隐藏")
        btn_toggle.clicked.connect(self.toggle_api_visibility)

        row = QHBoxLayout()
        row.addWidget(self.ed_api)
        row.addWidget(btn_toggle)
        wrow = QWidget()
        wrow.setLayout(row)

        f_key.addRow("API Key", wrow)
        layout.addWidget(g_key)

        # ====== 2) 图片选择区 ======
        g_img = QGroupBox("第 2 步：选择参考图片（1～4 张）")
        v_img = QVBoxLayout(g_img)

        btns = QHBoxLayout()
        btn_add = QPushButton("选择图片")
        btn_add.clicked.connect(self.add_images)

        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self.clear_images)

        btns.addWidget(btn_add)
        btns.addWidget(btn_clear)
        btns.addStretch(1)
        v_img.addLayout(btns)

        self.list_images = QListWidget()
        self.list_images.currentItemChanged.connect(self.on_image_selected)
        v_img.addWidget(self.list_images)

        self.preview = QLabel("预览区")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(200)
        self.preview.setStyleSheet("border: 1px solid #999;")
        v_img.addWidget(self.preview)

        layout.addWidget(g_img)

        # ====== 3) 文本描述 + 尺寸 ======
        g_prompt = QGroupBox("第 3 步：描述你想生成什么")
        f_prompt = QFormLayout(g_prompt)

        self.ed_prompt = QTextEdit()
        self.ed_prompt.setPlainText(
            self.cfg.get("prompt", "参考图片的风格与背景，生成：番茄炒蛋（更逼真、更好看）")
        )

        self.cb_size = QComboBox()
        self.cb_size.addItems(["1280*1280", "1024*1024", "768*1024", "1024*768"])
        self.cb_size.setCurrentText(self.cfg.get("size", "1280*1280"))

        f_prompt.addRow("一句话描述", self.ed_prompt)
        f_prompt.addRow("尺寸", self.cb_size)

        layout.addWidget(g_prompt)

        # ====== 4) 生成与输出 ======
        g_run = QGroupBox("第 4 步：点击生成（会自动保存结果与日志）")
        v_run = QVBoxLayout(g_run)

        row_run = QHBoxLayout()
        self.btn_run = QPushButton("开始生成")
        self.btn_run.clicked.connect(self.run_generate)

        self.btn_open = QPushButton("打开输出文件夹")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self.open_last_run_dir)

        row_run.addWidget(self.btn_run)
        row_run.addWidget(self.btn_open)
        row_run.addStretch(1)
        v_run.addLayout(row_run)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(160)
        v_run.addWidget(self.log)

        layout.addWidget(g_run)

        self.last_run_dir: Path | None = None
        self.resize(920, 880)

        # 首次提示
        QTimer.singleShot(200, self.ensure_api_key_hint)

    # ---------- UI helpers ----------
    def toggle_api_visibility(self):
        if self.ed_api.echoMode() == QLineEdit.Password:
            self.ed_api.setEchoMode(QLineEdit.Normal)
        else:
            self.ed_api.setEchoMode(QLineEdit.Password)

    def toast(self, msg: str):
        self.log.append(msg)

    def ensure_api_key_hint(self):
        if not self.ed_api.text().strip():
            QMessageBox.information(
                self,
                "首次使用提示",
                "请先粘贴 DashScope API Key。\n只需要一次，之后会自动记住。"
            )

    # ---------- image selection ----------
    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片（最多4张）",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*.*)"
        )
        if not files:
            return

        # 追加并截断到最多4张
        self.selected_images.extend(files)
        self.selected_images = self.selected_images[:4]
        self.refresh_image_list()

    def clear_images(self):
        self.selected_images = []
        self.refresh_image_list()
        self.preview.setText("预览区")

    def refresh_image_list(self):
        self.list_images.clear()
        for p in self.selected_images:
            self.list_images.addItem(QListWidgetItem(p))
        if self.selected_images:
            self.list_images.setCurrentRow(0)

    def on_image_selected(self, cur: QListWidgetItem, _prev: QListWidgetItem):
        if not cur:
            return
        path = cur.text()
        try:
            pix = QPixmap(path)
            if pix.isNull():
                self.preview.setText("无法预览该图片")
                return
            self.preview.setPixmap(pix.scaledToHeight(200, Qt.SmoothTransformation))
        except Exception:
            self.preview.setText("无法预览该图片")

    # ---------- core logic ----------
    def validate_constraints(self):
        api_key = self.ed_api.text().strip()
        if not api_key:
            raise ValueError("请先粘贴 API Key。")

        prompt = self.ed_prompt.toPlainText().strip()
        if not prompt:
            raise ValueError("请填写一句话描述。")

        imgs = list(self.selected_images)
        if not (1 <= len(imgs) <= 4):
            raise ValueError("请选择 1～4 张参考图片。")

        return api_key, prompt, imgs

    def default_output_base(self) -> Path:
        # 默认输出到桌面：~/Desktop/WanImageRuns
        return Path.home() / "Desktop" / "WanImageRuns"

    def build_image_inputs_base64(self, imgs: list[str]) -> list[str]:
        # 固定走 Base64 data URL（无需公网链接/OSS）
        return [file_to_data_url(p) for p in imgs]

    def make_payload(self, prompt: str, image_inputs: list[str]) -> dict:
        # 固定为图像编辑模式（enable_interleave=false），固定 n=1
        content = [{"text": prompt}]
        for img in image_inputs:
            content.append({"image": img})

        payload = {
            "model": "wan2.6-image",
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            },
            "parameters": {
                "prompt_extend": True,
                "watermark": False,
                "n": 1,
                "enable_interleave": False,
                "size": self.cb_size.currentText()
            }
        }
        return payload

    def open_folder(self, path: str):
        try:
            if sys.platform.startswith("darwin"):
                subprocess.run(["open", path])
            elif os.name == "nt":
                os.startfile(path)  # type: ignore
            else:
                subprocess.run(["xdg-open", path])
        except Exception:
            pass

    def open_last_run_dir(self):
        if self.last_run_dir and self.last_run_dir.exists():
            self.open_folder(str(self.last_run_dir))

    def run_generate(self):
        try:
            api_key, prompt, imgs = self.validate_constraints()
        except Exception as e:
            QMessageBox.critical(self, "无法开始", str(e))
            return

        # 自动记住 key / prompt / size（用户不需要点保存）
        self.cfg["api_key"] = api_key
        self.cfg["prompt"] = prompt
        self.cfg["size"] = self.cb_size.currentText()
        save_config(self.cfg)

        # 固定 region（不让用户选）
        region = "cn-beijing"

        out_base = self.default_output_base()
        run_dir = create_run_dir(str(out_base))
        self.last_run_dir = run_dir
        self.btn_open.setEnabled(True)

        http_log_path = run_dir / "http.log"

        self.toast(f"输出目录：{run_dir}")
        self.toast("复制输入图片...")
        copy_input_images(run_dir, imgs)

        try:
            self.toast("准备图片（Base64）...")
            image_inputs = self.build_image_inputs_base64(imgs)

            payload = self.make_payload(prompt, image_inputs)
            save_json(run_dir / "request.json", payload)

            self.toast("开始请求生成...")
            code, resp, headers = call_sync(api_key, region, payload)
            append_text(http_log_path, f"POST sync status={code}\nheaders={headers}\n\n")

            if not isinstance(resp, dict):
                save_json(run_dir / "response_raw.json", {"raw": resp})
                raise RuntimeError("接口返回不是 JSON，请查看 response_raw.json / http.log")

            save_json(run_dir / "response.json", resp)

            urls = extract_image_urls(resp)
            if not urls:
                self.toast("未找到图片结果链接。请打开输出目录查看 response.json。")
                QMessageBox.warning(self, "生成完成但未出图", f"请查看：{run_dir}/response.json")
                self.open_folder(str(run_dir))
                return

            self.toast(f"下载结果图片（{len(urls)} 张）...")
            saved = download_images(urls, str(run_dir))
            for p in saved:
                self.toast(f"已保存：{p}")

            QMessageBox.information(self, "完成", f"已生成并保存到：\n{run_dir}")
            self.open_folder(str(run_dir))

        except Exception as e:
            self.toast(f"ERROR: {e}")
            QMessageBox.critical(self, "生成失败", f"{e}\n\n日志与请求已保存到：\n{run_dir}")
            self.open_folder(str(run_dir))