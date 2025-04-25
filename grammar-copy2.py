import requests
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QMenu, QMessageBox, QPushButton, QLabel, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QAction, QIcon
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
import sys
import re
import json
import threading
import concurrent.futures

class GrammarCheckerThread(QThread):
    """Thread for handling grammar checking to keep UI responsive"""
    result_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, text):
        super().__init__()
        self.text = text
        
    def run(self):
        try:
            # Post the text to the LanguageTool server (running on localhost:8081)
            response = requests.post("http://localhost:8081/v2/check", data={
                "text": self.text,
                "language": "en-US",
                "enabledOnly": "false",
                "level": "picky"  # Most strict checking level
            }, timeout=3)  # Add timeout to prevent hanging
            
            if response.status_code != 200:
                self.error_occurred.emit(f"Server error: {response.status_code}")
                return
                
            result = response.json()
            self.result_ready.emit(result)
            
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"Connection error: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"Error: {str(e)}")


class GrammarRules:
    """Advanced grammar rules and instant fixes"""
    
    @staticmethod
    def apply_instant_fixes(text):
        """Apply instant grammar fixes without requiring server"""
        # Dictionary of common patterns and their fixes
        pattern_fixes = [
            # Fix specific "i name is" pattern
            (r'\bi name is\b', 'My name is'),
            
            # Fix capitalization at the beginning of sentences
            (r'(?:^|[.!?]\s+)([a-z])', lambda m: m.group(0).upper()),
            
            # Fix "i" to "I" when it's a pronoun
            (r'(?<!\w)\bi\b(?!\w)', 'I'),
            
            # Fix common possessive issues
            (r'\b(I|you|we|they|he|she|it)s\b', r'\1\'s'),
            
            # Fix "i am" capitalization
            (r'\bi am\b', 'I am'),
            
            # Fix consecutive duplicate words
            (r'\b(\w+)(\s+\1\b)+', r'\1'),
            
            # Fix missing spaces after punctuation
            (r'([.!?,;:])([A-Za-z])', r'\1 \2'),
            
            # Fix "its" vs "it's" common mistakes
            (r'\bits\s+(?:a|the|going|coming|true|false)\b', 'it\'s'),
            
            # Fix missing apostrophes in common contractions
            (r'\b(cant|wont|dont|didnt|couldnt|shouldnt|wouldnt|isnt|arent|wasnt|werent)\b', 
             lambda m: m.group(1).replace('nt', 'n\'t') if 'nt' in m.group(1) else m.group(1)[:-1] + '\'t'),
             
            # Fix double spaces
            (r'\s{2,}', ' '),
            
            # Fix "She going to school" to "She is going to school"
            (r'\b(She|He|It)\s+going\b', r'\1 is going'),
            
            # Fix "He don't like" to "He doesn't like"
            (r'\b(He|She|It)\s+don\'t\b', r'\1 doesn\'t'),
            
            # Fix "We was" to "We were"
            (r'\b(We|They|You)\s+was\b', r'\1 were'),
            
            # Fix "They is" to "They are"
            (r'\b(They|We|You)\s+is\b', r'\1 are'),
            
            # Fix "I am go" to "I am going"
            (r'\b(am|is|are)\s+go\b', r'\1 going'),
            
            # Fix "He have" to "He has"
            (r'\b(He|She|It)\s+have\b', r'\1 has'),
            
            # Fix "She can sings" to "She can sing"
            (r'\bcan\s+(\w+)s\b', r'can \1'),
            
            # Fix "This are" to "These are"
            (r'\bThis\s+are\b', 'These are'),
            
            # Fix "I am studied" to "I studied"
            (r'\b(am|is|are)\s+(\w+ed)\b', r'\2'),
            
            # Fix missing "the" in some common phrases
            (r'\bgoing to\s+(market|store|shop|mall|cinema|movies|theater|airport|station)\b', r'going to the \1'),
            
            # Add period at end of sentences if missing
            (r'([A-Za-z])$', r'\1.'),
        ]
        
        # Apply all quick fixes
        result = text
        for pattern, replacement in pattern_fixes:
            result = re.sub(pattern, replacement, result)
            
        # Apply sentence case to the first letter of the text if it starts with a lowercase
        if result and result[0].islower():
            result = result[0].upper() + result[1:]
            
        # Ensure proper spacing after punctuation
        result = re.sub(r'([.!?,;:])([A-Za-z])', r'\1 \2', result)
        
        # Ensure the text ends with proper punctuation
        if result and result[-1] not in ('.', '!', '?'):
            result += '.'
            
        return result
    
    @staticmethod
    def get_contextual_suggestions(text, position):
        """Get contextual grammar suggestions based on position in text"""
        # Extract the current sentence
        sentence_pattern = r'[^.!?]*[.!?]'
        sentences = re.findall(sentence_pattern, text)
        current_sentence = ""
        
        # Find which sentence contains the position
        current_pos = 0
        for sentence in sentences:
            if current_pos <= position < current_pos + len(sentence):
                current_sentence = sentence.strip()
                break
            current_pos += len(sentence)
        
        suggestions = []
        
        # Common grammar patterns to check
        patterns = [
            (r'\bi name is\b', "Pronoun-Verb Agreement", "Use 'My name is' instead of 'i name is'"),
            (r'(?<!\w)\bi\b(?!\w)', "Capitalization", "The pronoun 'I' should always be capitalized"),
            (r'\b(She|He|It)\s+going\b', "Missing Verb", "Use 'is going' instead of just 'going'"),
            (r'\b(He|She|It)\s+don\'t\b', "Subject-Verb Agreement", "Use 'doesn't' with singular subjects"),
            (r'\b(We|They|You)\s+was\b', "Subject-Verb Agreement", "Use 'were' with plural subjects"),
            (r'\b(They|We|You)\s+is\b', "Subject-Verb Agreement", "Use 'are' with plural subjects"),
            (r'\b(am|is|are)\s+go\b', "Verb Form", "Use 'going' after 'am/is/are'"),
            (r'\b(He|She|It)\s+have\b', "Subject-Verb Agreement", "Use 'has' with singular subjects"),
            (r'\bcan\s+(\w+)s\b', "Modal Verb Form", "Use base form of verb after modal verbs"),
            (r'\bThis\s+are\b', "Demonstrative Agreement", "Use 'These' with plural nouns"),
            (r'\b(am|is|are)\s+(\w+ed)\b', "Tense Error", "Don't use 'am/is/are' with past tense"),
        ]
        
        # Check for these patterns in the current sentence
        for pattern, label, advice in patterns:
            if re.search(pattern, current_sentence, re.IGNORECASE):
                suggestions.append((label, advice))
        
        # Check for ending punctuation
        if not current_sentence.endswith(('.', '!', '?')):
            suggestions.append(("Punctuation", "Sentences should end with proper punctuation"))
        
        return suggestions


class ErrorsList(QListWidget):
    """Widget that shows a list of all errors with clickable fixes"""
    error_selected = pyqtSignal(int, int, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.itemClicked.connect(self.on_item_clicked)
        self.errors = []
        
    def update_errors(self, errors):
        self.clear()
        self.errors = errors
        
        for i, error in enumerate(errors):
            message = error.get("message", "Unknown error")
            suggestions = error.get("replacements", [])
            
            if suggestions:
                suggest_text = suggestions[0].get("value", "")
                item_text = f"{message} → {suggest_text}"
            else:
                item_text = message
                
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store error index
            self.addItem(item)
            
    def on_item_clicked(self, item):
        error_index = item.data(Qt.ItemDataRole.UserRole)
        error = self.errors[error_index]
        offset = error["offset"]
        length = error["length"]
        
        suggestions = error.get("replacements", [])
        if suggestions:
            suggestion = suggestions[0].get("value", "")
            self.error_selected.emit(offset, length, suggestion)


class GrammarChecker:
    def __init__(self, text_edit: QTextEdit, errors_list: ErrorsList):
        self.text_edit = text_edit
        self.errors_list = errors_list
        self.text_edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self.show_context_menu)
        self.text_edit.textChanged.connect(self.on_text_changed)

        self.grammar_errors = []
        self.typing_timer = QTimer()
        self.typing_timer.setSingleShot(True)
        self.typing_timer.timeout.connect(self.check_grammar)
        
        # Connect errors list to fix function
        self.errors_list.error_selected.connect(self.replace_text)
        
        # Set a readable default font
        default_font = QFont("Arial", 12)
        self.text_edit.setFont(default_font)
        
        # Status indicator
        self.status_label = QLabel("Ready")
        
        # Flag to track if we're currently checking grammar
        self.is_checking = False
        
        # Set for tracking fixed errors to avoid duplicates
        self.fixed_errors = set()
        
        # Local grammar checks list (to use when server is unavailable)
        self.local_grammar_errors = []

    def on_text_changed(self):
        # Apply instant fixes for better user experience
        current_text = self.text_edit.toPlainText()
        cursor_position = self.text_edit.textCursor().position()
        
        # Only apply quick fixes if we have enough text and not in the middle of checking
        if len(current_text) > 1 and not self.is_checking:
            # Apply instant fixes without moving cursor
            fixed_text = GrammarRules.apply_instant_fixes(current_text)
            
            # Only update if something changed
            if fixed_text != current_text:
                self.is_checking = True
                cursor = self.text_edit.textCursor()
                self.text_edit.setPlainText(fixed_text)
                
                # Restore cursor position (adjust if needed)
                new_pos = min(cursor_position, len(fixed_text))
                cursor.setPosition(new_pos)
                self.text_edit.setTextCursor(cursor)
                self.is_checking = False
        
        # Restart the timer for comprehensive grammar check
        self.typing_timer.start(600)  # Check grammar 0.6 seconds after typing stops

    def check_grammar(self):
        text = self.text_edit.toPlainText()
        if not text.strip():  # Skip if text is empty
            return
            
        # Show checking status
        self.status_label.setText("Checking grammar...")
        self.is_checking = True
        
        # Perform local grammar checks
        self.perform_local_checks(text)
        
        # Start grammar checking in a separate thread
        self.checker_thread = GrammarCheckerThread(text)
        self.checker_thread.result_ready.connect(self.process_grammar_results)
        self.checker_thread.error_occurred.connect(self.handle_grammar_error)
        self.checker_thread.start()

    def perform_local_checks(self, text):
        """Perform basic grammar checks locally without relying on the server"""
        self.local_grammar_errors = []
        
        # Check for common grammatical patterns
        patterns = [
            (r'\bi name is\b', "Use 'My name is' instead", "My name is"),
            (r'\b(She|He|It)\s+going\b', "Missing 'is' before 'going'", lambda m: f"{m.group(1)} is going"),
            (r'\b(He|She|It)\s+don\'t\b', "Use 'doesn't' with singular subjects", lambda m: f"{m.group(1)} doesn't"),
            (r'\b(We|They|You)\s+was\b', "Use 'were' with plural subjects", lambda m: f"{m.group(1)} were"),
            (r'\b(They|We|You)\s+is\b', "Use 'are' with plural subjects", lambda m: f"{m.group(1)} are"),
            (r'\b(am|is|are)\s+go\b', "Use 'going' after 'am/is/are'", lambda m: f"{m.group(1)} going"),
            (r'\b(He|She|It)\s+have\b', "Use 'has' with singular subjects", lambda m: f"{m.group(1)} has"),
            (r'\bcan\s+(\w+)s\b', "Use base form after 'can'", lambda m: f"can {m.group(1)}"),
            (r'\bThis\s+are\b', "Use 'These' with plural", "These are"),
            (r'\b(I|He|She|It|We|They|You)\s+(am|is|are)\s+(\w+ed)\b', "Don't use 'am/is/are' with past tense", 
             lambda m: f"{m.group(1)} {m.group(3)}"),
        ]
        
        for pattern, message, replacement in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if callable(replacement):
                    replace_text = replacement(match)
                else:
                    replace_text = replacement
                    
                self.local_grammar_errors.append({
                    "message": message,
                    "offset": match.start(),
                    "length": match.end() - match.start(),
                    "replacements": [{"value": replace_text}],
                    "rule": {"id": f"LOCAL_{pattern}"}
                })
        
        # Sort errors by position
        self.local_grammar_errors.sort(key=lambda e: e["offset"])
        
        # Update the error list with local errors
        self.errors_list.update_errors(self.local_grammar_errors)
        
        # Highlight local errors
        self.grammar_errors = self.local_grammar_errors
        self.highlight_grammar_errors()
        self.status_label.setText(f"Found {len(self.local_grammar_errors)} issues (local check)")

    def process_grammar_results(self, result):
        # Combine server errors with local errors
        server_errors = result.get("matches", [])
        
        # Merge errors, preferring server errors if there's overlap
        all_errors = []
        server_positions = {(e["offset"], e["offset"] + e["length"]) for e in server_errors}
        
        # Add local errors that don't overlap with server errors
        for error in self.local_grammar_errors:
            start = error["offset"]
            end = start + error["length"]
            overlaps = any(s_start <= start < s_end or s_start < end <= s_end 
                           for s_start, s_end in server_positions)
            if not overlaps:
                all_errors.append(error)
                
        # Add all server errors
        all_errors.extend(server_errors)
        
        # Sort by position
        all_errors.sort(key=lambda e: e["offset"])
        
        self.grammar_errors = all_errors
        
        # Update errors list
        self.errors_list.update_errors(self.grammar_errors)
        
        self.highlight_grammar_errors()
        self.status_label.setText(f"Found {len(self.grammar_errors)} issues")
        self.is_checking = False

    def handle_grammar_error(self, error_message):
        # If server fails, use local checks only
        self.status_label.setText("Using basic grammar checks only")
        self.grammar_errors = self.local_grammar_errors
        self.is_checking = False

    def highlight_grammar_errors(self):
        cursor = self.text_edit.textCursor()
        cursor.beginEditBlock()

        # Store current cursor position
        current_position = cursor.position()

        # Clear previous formatting
        format_clear = QTextCharFormat()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(format_clear)
        cursor.clearSelection()

        # Highlight errors with red underlines
        for error in self.grammar_errors:
            offset = error["offset"]
            length = error["length"]
            fmt = QTextCharFormat()
            fmt.setUnderlineColor(QColor("red"))
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            
            # Add tooltip with error message and suggestion
            message = error.get("message", "Grammar error")
            suggestions = error.get("replacements", [])
            if suggestions:
                suggestion = suggestions[0].get("value", "")
                tooltip = f"{message}\nSuggestion: {suggestion}"
            else:
                tooltip = message
            fmt.setToolTip(tooltip)

            cursor.setPosition(offset)
            cursor.setPosition(offset + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.setCharFormat(fmt)

        # Restore cursor position
        cursor.setPosition(current_position)
        self.text_edit.setTextCursor(cursor)
        
        cursor.endEditBlock()

    def show_context_menu(self, position):
        cursor = self.text_edit.cursorForPosition(position)
        pos = cursor.position()

        # Check if the clicked position has a grammar error
        error_at_position = None
        for error in self.grammar_errors:
            start = error["offset"]
            end = start + error["length"]
            if start <= pos <= end:
                error_at_position = error
                break
                
        # If no error found at this position, show the regular context menu with grammar options
        if not error_at_position:
            menu = self.text_edit.createStandardContextMenu()
            
            # Add grammar check option at the top
            menu.insertSeparator(menu.actions()[0])
            check_action = QAction("Check Grammar", menu)
            check_action.triggered.connect(self.check_grammar)
            menu.insertAction(menu.actions()[0], check_action)
            
            # Get contextual suggestions
            text = self.text_edit.toPlainText()
            contextual_suggestions = GrammarRules.get_contextual_suggestions(text, pos)
            
            if contextual_suggestions:
                menu.addSeparator()
                suggestion_menu = QMenu("Writing Suggestions", menu)
                menu.addMenu(suggestion_menu)
                
                for category, suggestion in contextual_suggestions:
                    action = QAction(f"{category}: {suggestion}", menu)
                    action.setEnabled(False)  # These are just informational
                    suggestion_menu.addAction(action)
            
            menu.exec(self.text_edit.mapToGlobal(position))
            return

        # Create a custom context menu for grammar suggestions
        menu = QMenu(self.text_edit)
        
        # Add error message as a header (non-clickable)
        error_message = error_at_position.get("message", "Grammar error")
        title_action = QAction(f"✖ {error_message}", menu)
        title_action.setEnabled(False)
        font = title_action.font()
        font.setBold(True)
        title_action.setFont(font)
        menu.addAction(title_action)
        menu.addSeparator()
        
        # Add suggestions
        suggestions = error_at_position.get("replacements", [])
        if suggestions:
            for i, suggestion in enumerate(suggestions[:5]):  # Limit to 5 suggestions
                suggestion_text = suggestion.get("value", "")
                if suggestion_text:
                    action = QAction(f"✓ Change to: {suggestion_text}", menu)
                    # Using a lambda with default argument to avoid late binding issues
                    action.triggered.connect(
                        lambda checked, start=error_at_position["offset"],
                               length=error_at_position["length"],
                               text=suggestion_text: self.replace_text(start, length, text)
                    )
                    menu.addAction(action)
        else:
            no_suggestions = QAction("No suggestions available", menu)
            no_suggestions.setEnabled(False)
            menu.addAction(no_suggestions)
            
        menu.addSeparator()
        
        # Add option to ignore this error
        ignore_action = QAction("Ignore this error", menu)
        ignore_action.triggered.connect(
            lambda: self.ignore_error(error_at_position["offset"], error_at_position["length"])
        )
        menu.addAction(ignore_action)
        
        # Add option to fix all similar errors
        fix_all_action = QAction("Fix all similar errors", menu)
        rule_id = error_at_position.get("rule", {}).get("id", "")
        if rule_id and suggestions and suggestions[0].get("value"):
            fix_all_action.triggered.connect(
                lambda: self.fix_all_similar_errors(rule_id, suggestions[0].get("value"))
            )
            menu.addAction(fix_all_action)
        else:
            fix_all_action.setEnabled(False)
            menu.addAction(fix_all_action)
        
        menu.exec(self.text_edit.mapToGlobal(position))

    def replace_text(self, start, length, replacement):
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        self.text_edit.setTextCursor(cursor)  # Move cursor to the replacement
        
        # Re-check grammar after a short delay to allow the text to update
        QTimer.singleShot(100, self.check_grammar)

    def ignore_error(self, start, length):
        # Get the current error text
        cursor = self.text_edit.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
        
        # Remove highlighting for this specific error
        format_clear = QTextCharFormat()
        cursor.setCharFormat(format_clear)
        cursor.clearSelection()
        
        # Add to fixed errors set
        error_key = f"{start}:{length}"
        self.fixed_errors.add(error_key)
        
    def fix_all_similar_errors(self, rule_id, replacement):
        """Fix all errors with the same rule ID"""
        # Get all errors with the same rule ID
        similar_errors = [e for e in self.grammar_errors 
                         if e.get("rule", {}).get("id") == rule_id]
        
        # Sort by position in reverse order to avoid offset shifts
        similar_errors.sort(key=lambda e: e["offset"], reverse=True)
        
        # Fix all similar errors
        for error in similar_errors:
            self.replace_text(error["offset"], error["length"], replacement)
            
    def auto_fix_all(self):
        """Automatically fix all grammar issues with the first suggestion"""
        if not self.grammar_errors:
            return
            
        # Sort by position in reverse order to avoid offset shifts
        errors = sorted(self.grammar_errors, key=lambda e: e["offset"], reverse=True)
        
        for error in errors:
            suggestions = error.get("replacements", [])
            if suggestions and suggestions[0].get("value"):
                self.replace_text(error["offset"], error["length"], suggestions[0].get("value"))
                
        # Re-check grammar after all fixes
        QTimer.singleShot(100, self.check_grammar)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Grammar Checker")
        self.setGeometry(100, 100, 1000, 600)
        
        # Create main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Create text edit widget
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Type your text here. The grammar checker will automatically analyze your writing.")
        
        # Create errors list widget
        self.errors_list = ErrorsList()
        
        # Create grammar checker
        self.grammar_checker = GrammarChecker(self.text_edit, self.errors_list)
        
        # Create widget for the editor side
        editor_widget = QWidget()
        editor_layout = QVBoxLayout(editor_widget)
        
        # Create buttons layout
        button_layout = QHBoxLayout()
        
        # Add grammar check button
        check_button = QPushButton("Check Grammar")
        check_button.setIcon(QIcon.fromTheme("edit-find"))
        check_button.clicked.connect(self.grammar_checker.check_grammar)
        button_layout.addWidget(check_button)
        
        # Add auto-fix button
        auto_fix_button = QPushButton("Auto-Fix All")
        auto_fix_button.clicked.connect(self.grammar_checker.auto_fix_all)
        button_layout.addWidget(auto_fix_button)
        
        # Add example button
        example_button = QPushButton("Insert Example")
        example_button.clicked.connect(self.insert_example)
        button_layout.addWidget(example_button)
        
        # Add status label
        button_layout.addWidget(self.grammar_checker.status_label)
        
        # Add stretch to push status label to the right
        button_layout.addStretch()
        
        # Add widgets to editor layout
        editor_layout.addWidget(self.text_edit)
        editor_layout.addLayout(button_layout)
        
        # Create widget for the errors list side
        errors_widget = QWidget()
        errors_layout = QVBoxLayout(errors_widget)
        errors_layout.addWidget(QLabel("Grammar Issues:"))
        errors_layout.addWidget(self.errors_list)
        
        # Add widgets to splitter
        splitter.addWidget(editor_widget)
        splitter.addWidget(errors_widget)
        
        # Set initial splitter sizes (70% editor, 30% errors list)
        splitter.setSizes([700, 300])
        
        # Set central widget
        self.setCentralWidget(splitter)
        
        # Examples of common grammar errors (for the example button)
        self.example_texts = [
            "i name is Durga.",
            "She going to school.",
            "He don't like tea.",
            "We was late.",
            "They is happy.",
            "I am go to market.",
            "He have a car.",
            "She can sings well.",
            "This are my books.",
            "I am studied yesterday."
        ]
        
        # Start with an empty editor
        self.text_edit.clear()
        
    def insert_example(self):
        """Insert an example text with common grammar errors"""
        import random
        example = random.choice(self.example_texts)
        self.text_edit.setPlainText(example)
        self.grammar_checker.check_grammar()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Set fusion style for modern look
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())