# ------ Standard Libraries ------ #
import sys
import os
import json
import tempfile
import shutil
from urllib.parse import urlparse
import base64
import secrets
import queue
import threading
import requests
import time
from typing import List, Dict, Any, Optional, Tuple
import re

# ------ PyQt6 & GUI ------ #
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QFileDialog, QMessageBox,
    QVBoxLayout, QWidget, QMenu, QScrollArea, QPushButton, QInputDialog,
    QLabel, QLineEdit, QDialog, QGridLayout, QMenuBar, QWidgetAction,
    QToolTip, QStatusBar, QHBoxLayout, QProgressBar, QComboBox
)
from PyQt6.QtGui import QAction, QTextCursor, QFont, QColor, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt, QPoint, QRect

# ------ External Modules ------ #
import sounddevice as sd
import vosk
import json as js
from fpdf import FPDF
from deep_translator import GoogleTranslator
import docx

# ------ Encryption ------ #
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# ------ Whisper + Media Transcription ------ #
import whisper
import yt_dlp
import torch
import subprocess

# ====== Utility Functions ====== #
def generate_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())

def encrypt_data(data: bytes, password: str) -> bytes:
    salt = os.urandom(16)
    key = generate_key(password, salt)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(data) + encryptor.finalize()
    return salt + iv + encrypted

def decrypt_data(encrypted_data: bytes, password: str) -> bytes:
    salt = encrypted_data[:16]
    iv = encrypted_data[16:32]
    data = encrypted_data[32:]
    key = generate_key(password, salt)
    cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(data) + decryptor.finalize()

def is_url(path):
    try:
        result = urlparse(path)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def identify_platform(url):
    """Identify which social media platform a URL belongs to"""
    domain_patterns = {
        'youtube': r'(youtube\.com|youtu\.be)',
        'facebook': r'(facebook\.com|fb\.com|fb\.watch)',
        'instagram': r'(instagram\.com)',
        'twitter': r'(twitter\.com|x\.com)',
        'tiktok': r'(tiktok\.com)',
        'linkedin': r'(linkedin\.com)',
        'reddit': r'(reddit\.com)',
        'pinterest': r'(pinterest\.com)',
        'vimeo': r'(vimeo\.com)',
        'threads': r'(threads\.net)',
        'snapchat': r'(snapchat\.com)',
        'dailymotion': r'(dailymotion\.com)',
        'twitch': r'(twitch\.tv)',
        'soundcloud': r'(soundcloud\.com)',
        'spotify': r'(spotify\.com)',
        'discord': r'(discord\.com)',
    }
    
    for platform, pattern in domain_patterns.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    
    return "generic"

def download_media_from_url(url, progress_callback=None):
    """Download media from URL with platform-specific configurations"""
    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "%(title)s.%(ext)s")
    
    # Identify platform to apply appropriate settings
    platform = identify_platform(url)
    
    # Base options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'noplaylist': True,
        'no_warnings': False,
        'ignoreerrors': True,
        'cookiefile': None,  # Will be set if needed
    }
    
    # Add platform-specific options
    if platform == 'youtube':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'extract_flat': False,
        })
    elif platform in ['facebook', 'instagram', 'threads']:
        # Meta platforms often need more specific handling
        ydl_opts.update({
            'format': 'bestaudio/best',
            'extract_flat': True,
            'add_header': [
                'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            ],
        })
    elif platform == 'twitter':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'add_header': [
                'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            ],
        })
    elif platform == 'tiktok':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'add_header': [
                'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            ],
        })
    
    # Progress callback
    if progress_callback:
        def progress_hook(d):
            if d['status'] == 'downloading':
                if 'total_bytes' in d and d['total_bytes'] > 0:
                    percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                    progress_callback(percent)
                elif 'downloaded_bytes' in d:
                    # If total size is unknown, still show progress
                    progress_callback(-1)  # Signal indeterminate progress
                    
        ydl_opts['progress_hooks'] = [progress_hook]
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(url, download=True)
            if result:
                files = os.listdir(temp_dir)
                media_file = next((f for f in files if not f.endswith('.part')), None)
                if media_file:
                    return os.path.join(temp_dir, media_file)
                else:
                    return None
            else:
                raise Exception(f"Unable to extract info from {url}")
    except Exception as e:
        print(f"Error downloading from {platform}: {str(e)}")
        # Try with more aggressive options if first attempt failed
        try:
            ydl_opts.update({
                'quiet': False,
                'verbose': True,
                'force_generic_extractor': True
            })
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
                files = os.listdir(temp_dir)
                media_file = next((f for f in files if not f.endswith('.part')), None)
                return os.path.join(temp_dir, media_file) if media_file else None
        except Exception as e2:
            print(f"Second attempt failed: {str(e2)}")
            return None

def transcribe_with_whisper(media_path, progress_callback=None):
    """Transcribe media using Whisper model with progress reporting"""
    # Report loading model (10%)
    if progress_callback:
        progress_callback(10)
    
    model = whisper.load_model("base" if not torch.cuda.is_available() else "medium")
    
    # Report model loaded (30%)
    if progress_callback:
        progress_callback(30)
    
    # Transcribe with progress updates
    result = model.transcribe(media_path)
    
    # Report completion (100%)
    if progress_callback:
        progress_callback(100)
    
    return result["text"]

# ====== Grammar Checker Thread ====== #
class GrammarCheckerThread(QThread):
    results_ready = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.text_to_check = ""
        self.is_running = True
        self.check_requested = threading.Event()
        
    def set_text(self, text):
        self.text_to_check = text
        self.check_requested.set()
        
    def stop(self):
        self.is_running = False
        self.check_requested.set()
        
    def run(self):
        while self.is_running:
            # Wait for check request
            self.check_requested.wait()
            self.check_requested.clear()
            
            if not self.is_running:
                break
                
            text = self.text_to_check
            if not text.strip():
                continue
                
            try:
                response = requests.post(
                    "http://localhost:8081/v2/check", 
                    data={
                        "text": text,
                        "language": "en-US",
                        "enabledOnly": "false",
                        "level": "picky"  # Most strict checking level
                    }, 
                    timeout=3
                )
                
                if response.status_code == 200:
                    results = response.json().get("matches", [])
                    self.results_ready.emit(results)
            except Exception as e:
                print(f"Grammar check error: {str(e)}")
                
            # Add a small delay to prevent CPU overuse
            time.sleep(0.1)

# ====== Grammar Highlighter ====== #
class GrammarHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grammar_issues = []
        
    def set_grammar_issues(self, issues):
        self.grammar_issues = issues
        self.rehighlight()
        
    def highlightBlock(self, text):
        if not self.grammar_issues:
            return
            
        for issue in self.grammar_issues:
            start = issue.get("offset", 0)
            length = issue.get("length", 0)
            
            # Check if this issue is in the current block
            block_start = self.currentBlock().position()
            if start >= block_start and start < block_start + len(text):
                # Calculate relative position in this block
                relative_start = start - block_start
                
                # Make sure we don't go beyond the block length
                if relative_start + length > len(text):
                    length = len(text) - relative_start
                    
                if relative_start >= 0 and length > 0:
                    format = QTextCharFormat()
                    format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
                    format.setUnderlineColor(QColor("red"))
                    
                    self.setFormat(relative_start, length, format)

# ====== Grammar Check TextEdit ====== #
class GrammarCheckTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlighter = GrammarHighlighter(self.document())
        self.grammar_check_enabled = True
        self.grammar_checker = GrammarCheckerThread()
        self.grammar_checker.results_ready.connect(self.handle_grammar_results)
        self.grammar_checker.start()
        
        # Delayed grammar check timer
        self.grammar_timer = QTimer()
        self.grammar_timer.setSingleShot(True)
        self.grammar_timer.timeout.connect(self.delayed_grammar_check)
        
        # Connect text change signal to trigger delayed check
        self.textChanged.connect(self.handle_text_changed)
        
        # Setup context menu for grammar suggestions
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def handle_text_changed(self):
        """Handle text changes by scheduling a delayed grammar check"""
        if self.grammar_check_enabled:
            # Reset timer to delay grammar check (1 second after typing stops)
            self.grammar_timer.start(1000)
            
    def delayed_grammar_check(self):
        """Perform grammar check after delay"""
        if self.grammar_check_enabled:
            text = self.toPlainText()
            self.grammar_checker.set_text(text)
            
    def handle_grammar_results(self, issues):
        """Handle grammar check results"""
        self.highlighter.set_grammar_issues(issues)
        
    def show_context_menu(self, pos):
        """Show custom context menu with grammar suggestions"""
        cursor = self.cursorForPosition(pos)
        cursor_pos = cursor.position()
        
        # Check if cursor is on a grammar issue
        issues = self.highlighter.grammar_issues
        current_issue = None
        
        for issue in issues:
            start = issue.get("offset", 0)
            length = issue.get("length", 0)
            
            if start <= cursor_pos < start + length:
                current_issue = issue
                break
                
        # Create menu
        menu = self.createStandardContextMenu()
        
        # Add grammar suggestions if applicable
        if current_issue:
            menu.addSeparator()
            suggestions_menu = QMenu("Grammar Suggestions", self)
            
            # Add suggestions
            replacements = current_issue.get("replacements", [])
            for replacement in replacements[:5]:  # Limit to 5 suggestions
                suggestion = replacement.get("value", "")
                if suggestion:
                    action = suggestions_menu.addAction(suggestion)
                    action.triggered.connect(
                        lambda checked, s=suggestion, issue=current_issue: 
                        self.apply_suggestion(issue, s)
                    )
                    
            if replacements:
                menu.addMenu(suggestions_menu)
            else:
                action = menu.addAction("No suggestions available")
                action.setEnabled(False)
                
            # Add ignore action
            menu.addAction("Ignore", 
                          lambda issue=current_issue: self.ignore_issue(issue))
                
        # Show menu
        menu.exec(self.viewport().mapToGlobal(pos))
        
    def apply_suggestion(self, issue, suggestion):
        """Apply selected suggestion to text"""
        start = issue.get("offset", 0)
        length = issue.get("length", 0)
        
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, length)
        cursor.insertText(suggestion)
        
        # Update grammar check
        self.delayed_grammar_check()
        
    def ignore_issue(self, issue):
        """Ignore the current grammar issue"""
        issues = self.highlighter.grammar_issues.copy()
        issues.remove(issue)
        self.highlighter.set_grammar_issues(issues)
        
    def closeEvent(self, event):
        """Stop grammar checker thread on close"""
        self.grammar_checker.stop()
        self.grammar_checker.wait()
        super().closeEvent(event)

# ====== Voice Typing Thread ====== #
class VoiceTypingThread(QThread):
    text_output = pyqtSignal(str)

    def __init__(self, model_path):
        super().__init__()
        self.model_path = model_path
        self.running = True

    def run(self):
        q = queue.Queue()
        model = vosk.Model(self.model_path)
        samplerate = int(sd.query_devices(None, 'input')['default_samplerate'])

        def callback(indata, frames, time, status):
            q.put(bytes(indata))

        with sd.RawInputStream(samplerate=samplerate, blocksize=8000, dtype='int16',
                               channels=1, callback=callback):
            rec = vosk.KaldiRecognizer(model, samplerate)
            while self.running:
                data = q.get()
                if rec.AcceptWaveform(data):
                    result = js.loads(rec.Result())
                    if result.get("text"):
                        self.text_output.emit(result["text"])

    def stop(self):
        self.running = False

# ====== Media Downloader Thread ====== #
class MediaDownloaderThread(QThread):
    download_progress = pyqtSignal(float)
    download_complete = pyqtSignal(str)
    download_error = pyqtSignal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
    
    def run(self):
        try:
            media_path = download_media_from_url(self.url, self.report_progress)
            if media_path:
                self.download_complete.emit(media_path)
            else:
                self.download_error.emit(f"Failed to download media from {self.url}")
        except Exception as e:
            self.download_error.emit(f"Error downloading media: {str(e)}")
    
    def report_progress(self, percent):
        self.download_progress.emit(percent)

# ====== Transcription Thread ====== #
class TranscriptionThread(QThread):
    transcription_progress = pyqtSignal(float)
    transcription_complete = pyqtSignal(str)
    transcription_error = pyqtSignal(str)
    
    def __init__(self, media_path):
        super().__init__()
        self.media_path = media_path
    
    def run(self):
        try:
            text = transcribe_with_whisper(self.media_path, self.report_progress)
            self.transcription_complete.emit(text)
        except Exception as e:
            self.transcription_error.emit(f"Error transcribing media: {str(e)}")
    
    def report_progress(self, percent):
        self.transcription_progress.emit(percent)

# ====== Grammar Suggestion Dialog ====== #
class GrammarSuggestionDialog(QDialog):
    def __init__(self, issue, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Grammar Suggestion")
        self.setFixedWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Error message
        error_label = QLabel(f"Issue: {issue.get('message', 'Unknown issue')}")
        error_label.setWordWrap(True)
        layout.addWidget(error_label)
        
        # Replacements
        replacements = issue.get("replacements", [])
        if replacements:
            layout.addWidget(QLabel("Suggestions:"))
            
            buttons_layout = QVBoxLayout()
            for replacement in replacements[:5]:  # Limit to 5 suggestions
                suggestion = replacement.get("value", "")
                if suggestion:
                    btn = QPushButton(suggestion)
                    btn.clicked.connect(lambda _, s=suggestion: self.accept_suggestion(s))
                    buttons_layout.addWidget(btn)
            
            layout.addLayout(buttons_layout)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        self.selected_suggestion = None
        
    def accept_suggestion(self, suggestion):
        self.selected_suggestion = suggestion
        self.accept()

# ====== URL Input Dialog ====== #
class SocialMediaURLDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enter Social Media URL")
        self.setFixedWidth(500)
        
        layout = QVBoxLayout(self)
        
        # Platform selection
        platform_layout = QHBoxLayout()
        platform_layout.addWidget(QLabel("Platform:"))
        
        self.platform_combo = QComboBox()
        self.platform_combo.addItems([
            "Automatic Detection", 
            "YouTube", "Facebook", "Instagram", "Twitter/X", 
            "TikTok", "LinkedIn", "Pinterest", "Reddit", 
            "Vimeo", "Threads", "Snapchat", "Other"
        ])
        platform_layout.addWidget(self.platform_combo)
        layout.addLayout(platform_layout)
        
        # URL input
        layout.addWidget(QLabel("Enter URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://...")
        layout.addWidget(self.url_input)
        
        # URL examples
        examples_label = QLabel(
            "Examples:\n"
            "• YouTube: https://www.youtube.com/watch?v=abcdefg\n"
            "• Instagram: https://www.instagram.com/p/abcdefg/\n"
            "• Facebook: https://www.facebook.com/user/videos/123456\n"
            "• Twitter/X: https://x.com/username/status/123456\n"
            "• TikTok: https://www.tiktok.com/@user/video/123456"
        )
        examples_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(examples_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        download_btn = QPushButton("Download & Transcribe")
        download_btn.clicked.connect(self.accept)
        download_btn.setDefault(True)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(download_btn)
        layout.addLayout(button_layout)
        
    def get_url(self):
        return self.url_input.text().strip()
    
    def get_platform(self):
        platform = self.platform_combo.currentText()
        if platform == "Automatic Detection":
            return None
        elif platform == "Twitter/X":
            return "twitter"
        else:
            return platform.lower()

# ====== Progress Dialog ====== #
class TranscriptionProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Transcription Progress")
        self.setFixedSize(400, 150)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Status label
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignRight)
        
    def set_status(self, status):
        self.status_label.setText(status)
        
    def set_progress(self, value):
        if value < 0:  # Indeterminate progress
            self.progress_bar.setRange(0, 0)  # Makes it an "indeterminate" progress bar
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(value))

# ====== Main Application ====== #
class TextCraftAI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TextCraft AI")
        self.setGeometry(100, 100, 1000, 700)
        
        # Set up text edit with grammar checking
        self.text_edit = GrammarCheckTextEdit(self)
        self.setCentralWidget(self.text_edit)
        
        # Status bar for grammar information
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.grammar_status = QLabel("Grammar: Ready")
        self.status_bar.addWidget(self.grammar_status)
        
        # Initialize other variables
        self.model_path = r"C:\\Users\\avvar\\OneDrive\\Desktop\\textcraft_ai.py\\models\\vosk-model-small-en-us-0.15"
        self.voice_thread = None
        self.current_password = None
        self.recovery_key = None
        
        # Download and transcription threads
        self.download_thread = None
        self.transcription_thread = None
        
        # Create menu
        self.create_menu()
        
    def create_menu(self):
        menu_bar = self.menuBar()

        # File Menu
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("Open", self.open_file)
        file_menu.addAction("Save", self.save_file)
        file_menu.addAction("Save as PDF", self.save_pdf)
        file_menu.addAction("Save as DOC", self.save_doc)
        file_menu.addAction("Save History", self.save_history)

        # AI Menu
        ai_menu = menu_bar.addMenu("AI")
        ai_menu.addAction("Generate with AI", self.generate_with_ai)
        ai_menu.addAction("Summary with AI", self.summarize_ai)

        # Translator Menu
        translator_menu = menu_bar.addMenu("Translator")
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        grid_layout = QGridLayout(scroll_widget)
        languages = {
            'Assamese': 'as', 'Bengali': 'bn', 'Gujarati': 'gu', 'Hindi': 'hi', 'Kannada': 'kn',
            'Konkani': 'gom', 'Malayalam': 'ml', 'Manipuri': 'mni-Mtei', 'Marathi': 'mr', 'Nepali': 'ne',
            'Odia/Oriya': 'or', 'Punjabi': 'pa', 'Sanskrit': 'sa', 'Sindhi': 'sd', 'Tamil': 'ta',
            'Telugu': 'te', 'Urdu': 'ur', 'Dogri': 'doi', 'English': 'en', 'Mandarin Chinese': 'zh-CN',
            'Spanish': 'es', 'French': 'fr', 'Arabic': 'ar', 'Russian': 'ru', 'Portuguese': 'pt',
            'German': 'de', 'Japanese': 'ja', 'Korean': 'ko'
        }

        for i, (lang_name, lang_code) in enumerate(languages.items()):
            button = QPushButton(lang_name)
            button.clicked.connect(lambda checked, l=lang_code: self.translate_text(l))
            grid_layout.addWidget(button, i // 4, i % 4)

        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_widget)
        translator_action = QWidgetAction(self)
        translator_action.setDefaultWidget(scroll_area)
        translator_menu.addAction(translator_action)

        # Voice Menu
        voice_menu = menu_bar.addMenu("Voice")
        voice_menu.addAction("Start", self.start_voice_typing)
        voice_menu.addAction("Stop", self.stop_voice_typing)

        # Password Menu
        pass_menu = menu_bar.addMenu("Password")
        pass_menu.addAction("Set Password", self.set_password)
        pass_menu.addAction("Save Encrypted", self.save_encrypted_file)
        pass_menu.addAction("Open Encrypted", self.open_encrypted_file)

        # Social Media Menu
        social_menu = menu_bar.addMenu("Social Media")
        social_menu.addAction("Transcribe from URL", self.transcribe_from_url)
        
        # Original Whisper Menu (keep for backward compatibility)
        whisper_menu = menu_bar.addMenu("Audio/Video-Text")
        whisper_menu.addAction("Transcribe Audio/Video File", self.transcribe_media)
        whisper_menu.addAction("Transcribe from URL", self.transcribe_from_url)  # Add here too for discoverability
        
        # Grammar Menu
        grammar_menu = menu_bar.addMenu("Grammar")
        grammar_menu.addAction("Check Grammar", self.check_grammar)
        grammar_menu.addAction("Toggle Grammar Check", self.toggle_grammar_check)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Text Files (*.txt)")
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                self.text_edit.setText(f.read())

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.text_edit.toPlainText())

    def save_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF", "", "PDF Files (*.pdf)")
        if path:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            for line in self.text_edit.toPlainText().split('\n'):
                pdf.cell(200, 10, txt=line, ln=True)
            pdf.output(path)

    def save_doc(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save DOC", "", "Word Files (*.docx)")
        if path:
            doc = docx.Document()
            doc.add_paragraph(self.text_edit.toPlainText())
            doc.save(path)

    def save_history(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save History", "", "Text Files (*.txt)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.text_edit.toPlainText())

    def generate_with_ai(self):
        prompt = self.text_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "AI Warning", "Please enter some text to generate.")
            return

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama2", "prompt": prompt, "stream": True},
                stream=True
            )
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        json_data = json.loads(line.decode('utf-8'))
                        full_response += json_data.get("response", "")
                    except json.JSONDecodeError as e:
                        print("JSON decode error:", e)

            self.text_edit.append("\n\nAI: " + full_response.strip())
        except Exception as e:
            QMessageBox.critical(self, "AI Error", f"Error while generating content:\n{str(e)}")

    def summarize_ai(self):
        prompt = self.text_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "AI Warning", "Please enter some text to summarize.")
            return

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama2", "prompt": f"Summarize this: {prompt}", "stream": True},
                stream=True
            )
            response.raise_for_status()

            full_response = ""
            for line in response.iter_lines():
                if line:
                    try:
                        json_data = json.loads(line.decode('utf-8'))
                        full_response += json_data.get("response", "")
                    except json.JSONDecodeError as e:
                        print("JSON decode error:", e)

            self.text_edit.append("\n\nAI Summary: " + full_response.strip())
        except Exception as e:
            QMessageBox.critical(self, "AI Error", f"Error while generating summary:\n{str(e)}")

    def translate_text(self, lang_code):
        text = self.text_edit.toPlainText()
        if not text:
            QMessageBox.warning(self, "Translation Error", "No text to translate.")
            return

        try:
            translated = GoogleTranslator(source='auto', target=lang_code).translate(text)
            self.text_edit.setPlainText(translated)
        except Exception as e:
            QMessageBox.critical(self, "Translation Error", f"Error while translating:\n{str(e)}")

    def start_voice_typing(self):
        self.voice_thread = VoiceTypingThread(self.model_path)
        self.voice_thread.text_output.connect(self.append_voice_text)
        self.voice_thread.start()

    def stop_voice_typing(self):
        if self.voice_thread:
            self.voice_thread.stop()
            self.voice_thread.quit()
            self.voice_thread.wait()

    def append_voice_text(self, text):
        self.text_edit.append(text)

    def set_password(self):
        password, ok = QInputDialog.getText(self, "Set Password", "Enter Password:", 
                                          QLineEdit.EchoMode.Password)
        if ok and password:
            self.current_password = password
            # Generate recovery key
            self.recovery_key = secrets.token_hex(16)
            QMessageBox.information(self, "Recovery Key", 
                               f"Your recovery key is: {self.recovery_key}\n\n"
                               f"Save this key in a safe place. You will need it if you forget your password.")

    def save_encrypted_file(self):
        if not self.current_password:
            QMessageBox.warning(self, "Password Error", "Please set a password first.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save Encrypted File", "", "Encrypted Files (*.enc)")
        if path:
            try:
                # Encrypt the text content
                text_data = self.text_edit.toPlainText().encode('utf-8')
                encrypted_data = encrypt_data(text_data, self.current_password)
                
                # Save recovery information
                recovery_data = {
                    "recovery_key": self.recovery_key,
                    "created_at": time.time()
                }
                recovery_info = json.dumps(recovery_data).encode('utf-8')
                
                # Write to file - format: [recovery_info_size (4 bytes)][recovery_info][encrypted_data]
                with open(path, 'wb') as f:
                    recovery_size = len(recovery_info)
                    f.write(recovery_size.to_bytes(4, byteorder='big'))
                    f.write(recovery_info)
                    f.write(encrypted_data)
                
                QMessageBox.information(self, "Encryption Successful", 
                                     "File encrypted and saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Encryption Error", f"Error while encrypting file:\n{str(e)}")

    def open_encrypted_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Encrypted File", "", "Encrypted Files (*.enc)")
        if not path:
            return
            
        try:
            with open(path, 'rb') as f:
                # Read recovery info size and data
                recovery_size = int.from_bytes(f.read(4), byteorder='big')
                recovery_info = f.read(recovery_size)
                
                # Parse recovery info
                recovery_data = json.loads(recovery_info.decode('utf-8'))
                stored_recovery_key = recovery_data.get("recovery_key")
                
                # Read encrypted data
                encrypted_data = f.read()
                
            # Ask for password
            password, ok = QInputDialog.getText(self, "Enter Password", 
                                            "Enter password to decrypt:", 
                                            QLineEdit.EchoMode.Password)
            if not ok or not password:
                return
                
            try:
                # Try to decrypt with provided password
                decrypted_data = decrypt_data(encrypted_data, password)
                text = decrypted_data.decode('utf-8')
                self.text_edit.setText(text)
                self.current_password = password
                self.recovery_key = stored_recovery_key
                
                QMessageBox.information(self, "Decryption Successful", 
                                     "File decrypted successfully.")
            except Exception:
                # Password failed, ask if they want to use recovery key
                choice = QMessageBox.question(self, "Decryption Failed", 
                                         "Incorrect password. Do you want to try using the recovery key?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if choice == QMessageBox.StandardButton.Yes:
                    recovery, ok = QInputDialog.getText(self, "Recovery", 
                                                   "Enter your recovery key:")
                    if ok and recovery and recovery == stored_recovery_key:
                        # Reset password with recovery key
                        new_password, ok = QInputDialog.getText(self, "New Password", 
                                                        "Set a new password:", 
                                                        QLineEdit.EchoMode.Password)
                        if ok and new_password:
                            # Re-encrypt with new password
                            decrypted_data = decrypt_data(encrypted_data, password)
                            text = decrypted_data.decode('utf-8')
                            self.text_edit.setText(text)
                            self.current_password = new_password
                            
                            QMessageBox.information(self, "Recovery Successful", 
                                               "Recovery successful. New password set.")
                    else:
                        QMessageBox.critical(self, "Recovery Failed", 
                                        "Invalid recovery key.")
        except Exception as e:
            QMessageBox.critical(self, "Decryption Error", 
                             f"Error while opening encrypted file:\n{str(e)}")

    def transcribe_media(self):
        """Transcribe audio/video file with Whisper"""
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Open Audio/Video File", 
            "", 
            "Media Files (*.mp3 *.wav *.mp4 *.avi *.mkv *.webm *.m4a)"
        )
        
        if not path:
            return
        
        # Create progress dialog
        progress = TranscriptionProgressDialog(self)
        progress.set_status("Starting transcription...")
        
        # Create transcription thread
        self.transcription_thread = TranscriptionThread(path)
        
        # Connect signals
        self.transcription_thread.transcription_progress.connect(
            lambda p: progress.set_progress(p)
        )
        self.transcription_thread.transcription_complete.connect(
            lambda text: self.handle_transcription_complete(text, progress)
        )
        self.transcription_thread.transcription_error.connect(
            lambda err: self.handle_transcription_error(err, progress)
        )
        
        # Start transcription
        self.transcription_thread.start()
        
        # Show progress dialog (modal)
        result = progress.exec()
        
        # If dialog was rejected (cancel button), try to stop transcription
        if result == QDialog.DialogCode.Rejected and self.transcription_thread.isRunning():
            self.transcription_thread.terminate()
            QMessageBox.information(self, "Transcription", "Transcription cancelled.")

    def transcribe_from_url(self):
        """Transcribe media from social media URL"""
        # Show URL input dialog
        url_dialog = SocialMediaURLDialog(self)
        if url_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        
        url = url_dialog.get_url()
        if not url or not is_url(url):
            QMessageBox.warning(self, "URL Error", "Please enter a valid URL.")
            return
        
        # Create progress dialog
        progress = TranscriptionProgressDialog(self)
        progress.set_status("Downloading media...")
        progress.show()
        
        # Create download thread
        self.download_thread = MediaDownloaderThread(url)
        
        # Connect download signals
        self.download_thread.download_progress.connect(
            lambda p: self.handle_download_progress(p, progress)
        )
        self.download_thread.download_complete.connect(
            lambda path: self.handle_download_complete(path, progress)
        )
        self.download_thread.download_error.connect(
            lambda err: self.handle_download_error(err, progress)
        )
        
        # Start download
        self.download_thread.start()

    def handle_download_progress(self, percent, dialog):
        """Handle download progress updates"""
        if percent < 0:
            dialog.set_status("Downloading media... (size unknown)")
            dialog.set_progress(-1)
        else:
            dialog.set_status(f"Downloading media... {int(percent)}%")
            dialog.set_progress(percent)

    def handle_download_complete(self, media_path, dialog):
        """Handle completed download, start transcription"""
        dialog.set_status("Starting transcription...")
        dialog.set_progress(0)
        
        # Create transcription thread
        self.transcription_thread = TranscriptionThread(media_path)
        
        # Connect transcription signals
        self.transcription_thread.transcription_progress.connect(
            lambda p: dialog.set_progress(p)
        )
        self.transcription_thread.transcription_complete.connect(
            lambda text: self.handle_transcription_complete(text, dialog)
        )
        self.transcription_thread.transcription_error.connect(
            lambda err: self.handle_transcription_error(err, dialog)
        )
        
        # Start transcription
        self.transcription_thread.start()

    def handle_download_error(self, error, dialog):
        """Handle download errors"""
        dialog.hide()
        QMessageBox.critical(self, "Download Error", error)

    def handle_transcription_complete(self, text, dialog):
        """Handle completed transcription"""
        dialog.hide()
        self.text_edit.setText(text)
        QMessageBox.information(self, "Transcription", "Transcription completed successfully.")

    def handle_transcription_error(self, error, dialog):
        """Handle transcription errors"""
        dialog.hide()
        QMessageBox.critical(self, "Transcription Error", error)

    def check_grammar(self):
        """Manually trigger grammar check"""
        if hasattr(self.text_edit, 'delayed_grammar_check'):
            self.text_edit.delayed_grammar_check()
            QMessageBox.information(self, "Grammar Check", "Grammar check in progress.")

    def toggle_grammar_check(self):
        """Toggle automatic grammar checking"""
        if hasattr(self.text_edit, 'grammar_check_enabled'):
            self.text_edit.grammar_check_enabled = not self.text_edit.grammar_check_enabled
            status = "enabled" if self.text_edit.grammar_check_enabled else "disabled"
            QMessageBox.information(self, "Grammar Check", f"Automatic grammar check {status}.")
            
            # Update status bar
            if self.text_edit.grammar_check_enabled:
                self.grammar_status.setText("Grammar: Ready")
                self.text_edit.delayed_grammar_check()
            else:
                self.grammar_status.setText("Grammar: Disabled")
                # Clear highlighting
                self.text_edit.highlighter.set_grammar_issues([])

# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look and feel
    
    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = TextCraftAI()
    window.show()
    sys.exit(app.exec())