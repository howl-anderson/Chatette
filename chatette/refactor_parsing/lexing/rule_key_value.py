# coding: utf-8
"""
Module `chatette.refactor_parsing.lexing.rule_key_value`
Contains the definition of the class that represents the lexing rule
to tokenize a key or a value inside an annotation.
"""

from chatette.refactor_parsing.lexing.lexing_rule import LexingRule
from chatette.refactor_parsing.lexing import LexicalToken, TerminalType
from chatette.refactor_parsing.utils import \
    ANNOTATION_END, KEY_VAL_CONNECTOR, KEY_VAL_ENCLOSERS, find_unescaped
from chatette.utils import min_if_exist


class RuleKeyValue(LexingRule):
    def _apply_strategy(self, extract_key=True):
        """
        `extract_key` is a boolean that is `True` if this rule should extract 
        a key and `False` if this rule should extract a value.
        """
        if extract_key:
            terminal_type = TerminalType.key
        else:
            terminal_type = TerminalType.value

        encloser = None
        for current_encloser in KEY_VAL_ENCLOSERS:
            if self._text.startswith(current_encloser, self._next_index):
                self._next_index += 1
                encloser = current_encloser
        
        if encloser is not None:
            # Enclosed key/value
            next_encloser_index = \
                find_unescaped(self._text, encloser, self._next_index)
            if next_encloser_index is None:
                self.error_msg = \
                    "Missing key-value encloser. Expected symbol " + encloser + \
                    " instead of end of line."
                return False

            extracted_text = self._text[self._start_index+1:next_encloser_index]
            self._next_index = next_encloser_index + 1
            self._tokens.append(LexicalToken(terminal_type, extracted_text))
            return True
        else:
            # Key/value not enclosed
            next_connector_index = \
                find_unescaped(self._text, KEY_VAL_CONNECTOR, self._next_index)
            end_annotation_index = \
                find_unescaped(self._text, ANNOTATION_END, self._next_index)
            end_key_value_index = \
                min_if_exist(next_connector_index, end_annotation_index)
            if end_key_value_index is None:
                self.error_msg = \
                    "Couldn't find end of key/value. " + \
                    "Didn't expect the end of the line there."
                return False
            
            extracted_text = \
                self._text[self._start_index:end_key_value_index + 1].rstrip()
            self._next_index += len(extracted_text)
            self._tokens.append(LexicalToken(terminal_type, extracted_text))
            return True
