# coding: utf-8
"""
Module `chatette.refactor_parsing.lexing.rule_annotation`
Contains the definition of the class that represents the lexing rule
to tokenize an annotation (binded to an intent definition).
"""

from chatette.refactor_parsing.lexing.lexing_rule import LexingRule
from chatette.refactor_parsing.lexing import LexicalToken, TerminalType
from chatette.refactor_parsing.utils import \
    ANNOTATION_START, ANNOTATION_END, ANNOTATION_SEP, KEY_VAL_CONNECTOR, \
    extract_annotation_key_value, remove_enclosers

from chatette.refactor_parsing.lexing.rule_whitespaces import RuleWhitespaces
from chatette.refactor_parsing.lexing.rule_key_value import RuleKeyValue


class RuleAnnotation(LexingRule):
    def _apply_strategy(self):
        if self._text.startswith(ANNOTATION_START, self._next_index):
            self._next_index += 1
            self._tokens.append(
                LexicalToken(TerminalType.annotation_start, ANNOTATION_START)
            )
        else:
            self.error_msg = \
                "Invalid token. Expected an annotation there (starting with '" + \
                ANNOTATION_START + "')."
            return False
        
        whitespaces_rule = RuleWhitespaces(self._text, self._next_index)
        if whitespaces_rule.matches():
            self._next_index = whitespaces_rule.get_next_index_to_match()
            # Ignoring the tokens because whitespaces here are not meaningful
        
        # Empty annotation
        if self._text.startswith(ANNOTATION_END, self._next_index):
            self._next_index += 1
            self._tokens.append(
                LexicalToken(TerminalType.annotation_end, ANNOTATION_END)
            )
            return True

        first_key_val_rule = RuleKeyValue(self._text, self._next_index)
        if not first_key_val_rule.matches():
            self.error_msg = first_key_val_rule.error_msg
            return False
        self._next_index = first_key_val_rule.get_next_index_to_match()

        whitespaces_rule = RuleWhitespaces(self._text, self._next_index)
        if whitespaces_rule.matches():
            self._next_index = whitespaces_rule.get_next_index_to_match()
            # Ignoring the tokens because whitespaces here are not meaningful

        if not self._text.startswith(KEY_VAL_CONNECTOR, self._next_index):
            # Single value
            value_token = first_key_val_rule.get_lexical_tokens()[0]
            value_token.type = TerminalType.value
            self._tokens.append(value_token)
        else:
            # Multiple key/value pairs
            self._next_index += 1
            self._tokens.append(
                LexicalToken(
                    TerminalType.key_value_connector, KEY_VAL_CONNECTOR
                )
            )

            whitespaces_rule = RuleWhitespaces(self._text, self._next_index)
            if whitespaces_rule.matches():
                self._next_index = whitespaces_rule.get_next_index_to_match()
                # Ignoring the tokens because whitespaces here are not meaningful

            first_val_rule = RuleKeyValue(self._text, self._next_index)
            if not first_val_rule.matches(extract_key=False):
                self.error_msg = first_val_rule.error_msg
                return False
            
            self._next_index = first_val_rule.get_next_index_to_match()
            self._tokens.extend(first_key_val_rule.get_lexical_tokens())

            whitespaces_rule = RuleWhitespaces(self._text, self._next_index)
            if whitespaces_rule.matches():
                self._next_index = whitespaces_rule.get_next_index_to_match()
                # Ignoring the tokens because whitespaces here are not meaningful
            
            while self._text.startswith(ANNOTATION_SEP, self._next_index):
                whitespaces_rule = RuleWhitespaces(self._text, self._next_index)
                if whitespaces_rule.matches():
                    self._next_index = whitespaces_rule.get_next_index_to_match()
                    # Ignoring the tokens because whitespaces here are not meaningful

                key_rule = RuleKeyValue(self._text, self._next_index)
                if not key_rule.matches(extract_key=True):
                    self.error_msg = key_rule.error_msg
                    return False
                self._next_index = key_rule.get_next_index_to_match()
                self._tokens.extend(key_rule.get_lexical_tokens())

                whitespaces_rule = RuleWhitespaces(self._text, self._next_index)
                if whitespaces_rule.matches():
                    self._next_index = whitespaces_rule.get_next_index_to_match()
                    # Ignoring the tokens because whitespaces here are not meaningful
                
                if not self._text.startswith(KEY_VAL_CONNECTOR, self._next_index):
                    self.error_msg = \
                        "Cannot mix key-value pairs and single values " + \
                        "in annotations. Expected a key-value connector " + \
                        "(using symbol '" + KEY_VAL_CONNECTOR + "')."
                    return False
                self._next_index += 1
                self._tokens.append(
                    LexicalToken(
                        TerminalType.key_value_connector, KEY_VAL_CONNECTOR
                    )
                )

                whitespaces_rule = RuleWhitespaces(self._text, self._next_index)
                if whitespaces_rule.matches():
                    self._next_index = whitespaces_rule.get_next_index_to_match()
                    # Ignoring the tokens because whitespaces here are not meaningful

                value_rule = RuleKeyValue(self._text, self._next_index)
                if not value_rule.matches(extract_key=True):
                    self.error_msg = value_rule.error_msg
                    return False
                self._next_index = value_rule.get_next_index_to_match()
                self._tokens.extend(value_rule.get_lexical_tokens())

                whitespaces_rule = RuleWhitespaces(self._text, self._next_index)
                if whitespaces_rule.matches():
                    self._next_index = whitespaces_rule.get_next_index_to_match()
                    # Ignoring the tokens because whitespaces here are not meaningful
        
        if not self._text.startswith(ANNOTATION_END, self._next_index):
            self.error_msg = \
                "Invalid token. Expected the annotation to end there (using " + \
                "character ')')."
            return False
        self._next_index += 1
        self._tokens.append(
            LexicalToken(TerminalType.annotation_end, ANNOTATION_END)
        )
        return True
