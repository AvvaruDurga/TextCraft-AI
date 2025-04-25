import sys
import pyttsx3
import speech_recognition as sr
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QAction, QFileDialog,
    QMessageBox
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt


class TextCraftAI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TextCraft AI - AI-Powered Text Editor")
        self.setGeometry(100, 100, 800, 600)

        self.text_edit = QTextEdit()
        self.setCentralWidget(self.text_edit)

        self.engine = pyttsx3.init()

        self.create_menu()

    def create_menu(self):
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_file)
        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)

        # Speak
        speak_menu = menu_bar.addMenu("Speak")
        speak_action = QAction("Speak Text", self)
        speak_action.triggered.connect(self.speak_text)
        speak_menu.addAction(speak_action)

        # Voice Input
        voice_menu = menu_bar.addMenu("Voice")
        voice_input_action = QAction("Start Voice Typing", self)
        voice_input_action.triggered.connect(self.voice_to_text)
        voice_menu.addAction(voice_input_action)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            try:
                with open(path, 'r') as file:
                    content = file.read()
                    self.text_edit.setPlainText(content)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file:\n{str(e)}")

    def save_file(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            try:
                with open(path, 'w') as file:
                    file.write(self.text_edit.toPlainText())
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save file:\n{str(e)}")

    def speak_text(self):
        text = self.text_edit.toPlainText()
        if text:
            self.engine.say(text)
            self.engine.runAndWait()
        else:
            QMessageBox.information(self, "Speak Text", "There's no text to read.")

    def voice_to_text(self):
        recognizer = sr.Recognizer()
        mic = sr.Microphone()

        try:
            with mic as source:
                QMessageBox.information(self, "Voice Input", "Listening... Please speak into the microphone.")
                recognizer.adjust_for_ambient_noise(source)
                audio = recognizer.listen(source)

            text = recognizer.recognize_google(audio)
            self.text_edit.insertPlainText(text + " ")

        except sr.UnknownValueError:
            QMessageBox.critical(self, "Voice Input", "Sorry, I could not understand what you said.")
        except sr.RequestError:
            QMessageBox.critical(self, "Voice Input", "Could not request results from Google Speech Recognition.")
        except Exception as e:
            QMessageBox.critical(self, "Voice Input", f"An error occurred:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TextCraftAI()
    window.show()
    sys.exit(app.exec_())
