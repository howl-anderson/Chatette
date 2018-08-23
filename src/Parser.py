#!/usr/bin/env python3

import re
import os
import warnings

from utils import *
from parser_utils import *

from units.words import WordRuleContent, WordGroupRuleContent
from units.alias import AliasDefinition, AliasRuleContent
from units.slot import SlotDefinition, SlotRuleContent, DummySlotValRuleContent
from units.intent import IntentDefinition, IntentRuleContent


class Parser():
    """
    This class will parse the input file(s)
    and create an internal representation of its contents.
    """
    def __init__(self, input_file):
        self.in_file = input_file
        self.opened_files = []
        self.line_nb = 0
        self.line_counts_per_file = []

        self.aliases = dict()  # for each alias, stores a list of list of units
        self.slots = dict()  # for each slot, stores a list of value name and unit
        self.intents = dict()  # for each intent, stores a list of list of slots

        self.alias_definitions = []  # TODO redo as OOP
        self.slots_definitions = []
        self.intents_definitions = []

        self.parsing_finished = False


    def read_line(self):
        self.line_nb += 1
        return self.in_file.readline()
    def peek_line(self):
        """Returns the next line without moving forward in the file"""
        saved_pos = self.in_file.tell()
        line = self.in_file.readline()
        self.in_file.seek(saved_pos)
        return line

    def is_inside_decl(self):
        next_line = self.peek_line()
        return (next_line.startswith(' ') or next_line.startswith('\t'))


    def parse_file(self, filename):
        """Runs the parsing of the file `filename` within the same parser"""
        # Save current file info
        self.opened_files.append(self.in_file)
        self.line_counts_per_file.append(self.line_nb)
        # Open and parse new file
        self.line_nb = 0
        file_path = os.path.join(os.path.dirname(self.in_file.name), filename)
        with open(file_path, 'r') as in_file:
            self.in_file = in_file
            self.parse()
        # Restore last file info
        self.in_file = self.opened_files.pop()


    def parse(self):
        printDBG("Parsing file: "+self.in_file.name)
        line = None
        while line != "":
            line = self.read_line()
            stripped_line = line.lstrip()
            line_type = self.get_top_level_line_type(line, stripped_line)

            if line_type == LineType.empty or line_type == LineType.comment:
                continue
            stripped_line = strip_comments(stripped_line)  # Not done before to compute the indentation
            if line_type == LineType.include_file:
                self.parse_file(stripped_line[1:].rstrip())
            elif line_type == LineType.alias_declaration:
                self.parse_alias_definition(stripped_line)
            elif line_type == LineType.slot_declaration:
                self.parse_slot_definition(stripped_line)
            else:  # intent declaration
                self.parse_intent_definition(stripped_line)

        printDBG("Parsing of file: "+self.in_file.name+" finished")
        self.parsing_finished = True

    def parse_unit(self, unit):
        """
        Parses a unit (left stripped) and returns
        (unit name, arg, variation, randgen, percentgen, casegen)
        with `None` values for those not provided in the file.
        NB: `casegen` is a boolean.
        For a word group, the name will be its text.
        If an anonymous randgen is used '' will be its value.
        """
        name = None
        arg = None
        variation = None
        randgen = None
        percentgen = None
        casegen = False
        one_found = False
        for match in pattern_modifiers.finditer(unit):
            start_index = match.start()
            if one_found:  # this error would happen only when `unit` is a whole line (i.e. a declaration)
                raise SyntaxError("Expected only one unit here: only one declaration is allowed per line",
                    (self.in_file.name, self.line_nb, start_index, unit))
            else:
                one_found = True
            match = match.groupdict()

            name = match["name"]
            arg = match["arg"]
            variation = match["variation"]
            randgen = match["randgen"]
            percentgen = match["percentgen"]
            casegen = (match["casegen"] is not None)
            if name == "":
                raise SyntaxError("Units must have a name (or a content for word groups)",
                    (self.in_file.name, self.line_nb, start_index, unit))
            if arg == "":
                raise SyntaxError("Unnamed argument or unescaped colon (:)",
                    (self.in_file.name, self.line_nb, start_index, unit))
            if variation == "":
                raise SyntaxError("Precision must be named (e.g. [text#variation])",
                    (self.in_file.name, self.line_nb, start_index, unit))
            if percentgen == "":
                raise SyntaxError("Percentage for generation cannot be empty",
                    (self.in_file.name, self.line_nb, start_index, unit))
            if match["casegen"] != '&':
                raise SyntaxError("Unable to understand the symbols you used "+
                    "for case generation (should be '&')",
                    (self.in_file.name, self.line_nb, start_index, unit))

        return (name, arg, variation, randgen, percentgen, casegen)

    def parse_choice(self, text):
        """Parses a choice (as a str) and returns a list of inside str"""
        # TODO this code is broken
        no_leading_space = i == 0 or (i != 0 and words_and_units_raw[i-1] != ' ')
        choices = []
        splits = re.split(r"(?<!\\)/", string[1:-1])  # TODO improve the regex here
        # Manage randgen
        randgen = False
        if len(splits[-1]) >= 1 and splits[-1][-1] == RAND_GEN_SYM:
            if not (len(splits[-1]) >= 2 and splits[-1][-2] == ESCAPE_SYM):
                splits[-1] = splits[-1][:-1]
                randgen = True
        for choice_str in splits:
            if choice_str is not None and choice_str != "":  # TODO check the type of each choice?
                choices.append(self.split_contents(choice_str))
            else:
                raise SyntaxError("Empty choice not allowed in choices",
                    (self.in_file.name, self.line_nb, 0, name))
        if choices != []:
            words_and_units.append({
                "type": Unit.choice,
                "randgen": randgen,
                "choices": choices,
                "leading-space": not no_leading_space,
            })

    def parse_alias_definition(self, first_line):  # Lots of copy-paste in three methods
        """
        Parses the definition of an alias (declaration and contents)
        and adds the relevant info to the list of aliases.
        """
        # printDBG("alias: "+first_line.strip())
        # Manage the alias declaration
        (alias_name, alias_arg, alias_variation, randgen, percentgen, casegen) = \
            self.parse_unit(first_line)
        if alias_name is None or alias_name == "":
            raise SyntaxError("Aliases must be named",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if alias_arg == "":
            raise SyntaxError("Arguments must be named",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if alias_variation in RESERVED_VARIATION_NAMES:
            raise SyntaxError("You cannot use the reserved variation names: "+
                    str(RESERVED_VARIATION_NAMES),
                    (self.in_file.name, self.line_nb, 0, first_line))
        if randgen is not None:
            raise SyntaxError("Declarations cannot have a named random generation modifier",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if percentgen is not None:
            raise SyntaxError("Declarations cannot have a random generation modifier",
                    (self.in_file.name, self.line_nb, 0, first_line))

        # Manage the contents
        rules = []
        indentation_nb = None
        while self.is_inside_decl():
            line = self.read_line()
            stripped_line = line.lstrip()
            indentation_nb = self.check_indentation(indentation_nb, line, stripped_line)
            stripped_line = strip_comments(stripped_line)

            rules.append(self.split_contents(stripped_line))

        # Put the new definition inside the dict with aliases definitions
        if alias_name not in self.alias_definitions:
            if alias_variation is not None:
                self.alias_definitions[alias_name] = \
                    AliasDefinition(alias_name, rules, alias_arg, casegen)
            else:
                new_definition = \
                    AliasDefinition(alias_name, [], alias_arg, casegen)
                new_definition.add_rules(rules, alias_variation)
                self.alias_definitions[alias_name] = new_definition
        else:
            self.alias_definitions[alias_name].add_rules(rules, alias_variation)

    def parse_slot_definition(self, first_line):
        """
        Parses the definition of a slot (declaration and contents)
        and adds the relevant info to the list of slots.
        """
        # printDBG("slot: "+first_line.strip())
        #Manage the slot declaration
        (slot_name, slot_arg, slot_variation, randgen, percentgen, casegen) = \
            self.parse_unit(first_line)
        if slot_name is None or slot_name == "":
            raise SyntaxError("Slots must be named",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if slot_arg == "":
            raise SyntaxError("Arguments must be named",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if slot_variation in RESERVED_VARIATION_NAMES:
            raise SyntaxError("You cannot use the reserved variation names: "+str(RESERVED_VARIATION_NAMES),
                    (self.in_file.name, self.line_nb, 0, first_line))
        if randgen is not None:
            raise SyntaxError("Declarations cannot have a named random generation modifier",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if percentgen is not None:
            raise SyntaxError("Declarations cannot have a random generation modifier",
                    (self.in_file.name, self.line_nb, 0, first_line))

        #Manage the contents
        rules = []
        indentation_nb = None
        while self.is_inside_decl():
            line = self.read_line()
            stripped_line = line.lstrip()
            indentation_nb = self.check_indentation(indentation_nb, line, stripped_line)
            stripped_line = strip_comments(stripped_line)
            if stripped_line == "":
                continue

            (slot_val, rules) = \
                self.split_contents(stripped_line, accept_slot_val=True)
            if len(rules) <= 0:
                return
            if slot_val is None:  # Take the name of the first unit
                slot_val = rule[0].name
            rules.insert(0, DummySlotValRuleContent(slot_val))

        # Put the new definition inside the dict with slots definitions
        if slot_name not in self.slot_definitions:
            if slot_variation is not None:
                self.slot_definitions[slot_name] = \
                    SlotDefinition(slot_name, rules, slot_arg, casegen)
            else:
                new_definition = \
                    SlotDefinition(slot_name, [], slot_arg, casegen)
                new_definition.add_rules(rules, slot_variation)
                self.slot_definitions[slot_name] = new_definition
        else:
            self.slot_definitions[slot_name].add_rules(rules, slot_variation)

    def parse_intent_definition(self, first_line):
        """
        Parses the definition of an intent (declaration and contents)
        and adds the relevant info to the list of intents.
        """
        # printDBG("intent: "+first_line.strip())
        # Manage the intent declaration
        (intent_name, intent_arg, intent_variation, randgen, percentgen, casegen) = \
            self.parse_unit(first_line)
        if intent_name is None or intent_name == "":
            raise SyntaxError("Intents must be named",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if intent_arg == "":
            raise SyntaxError("Arguments must be named",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if intent_variation in RESERVED_VARIATION_NAMES:
            raise SyntaxError("You cannot use the reserved variation names: "+str(RESERVED_VARIATION_NAMES),
                    (self.in_file.name, self.line_nb, 0, first_line))
        if randgen is not None:
            raise SyntaxError("Declarations cannot have a named random generation modifier",
                    (self.in_file.name, self.line_nb, 0, first_line))
        if percentgen is not None:
            raise SyntaxError("Declarations cannot have a random generation modifier",
                    (self.in_file.name, self.line_nb, 0, first_line))

        nb_gen_asked = find_nb_gen_asked(first_line)

        # Manage the contents
        rules = []
        indentation_nb = None
        while self.is_inside_decl():
            line = self.read_line()
            stripped_line = line.lstrip()
            indentation_nb = self.check_indentation(indentation_nb, line, stripped_line)
            stripped_line = strip_comments(stripped_line)

            rules.append(self.split_contents(stripped_line))

        # Put the new definition inside the dict with intents definitions
        if intent_name not in self.intent_definitions:
            if intent_variation is not None:
                self.intent_definitions[intent_name] = \
                    IntentDefinition(intent_name, rules, intent_arg, casegen)
            else:
                new_definition = \
                    IntentDefinition(intent_name, [], intent_arg, casegen)
                new_definition.add_rules(rules, intent_variation)
                self.intent_definitions[intent_name] = new_definition
        else:
            self.intent_definitions[intent_name].add_rules(rules, intent_variation)


    #=========== Getters =================
    def has_parsed(self):
        return self.parsing_finished

    def get_definition(self, def_name, type):
        def_list = None
        if type == Unit.alias:
            def_list = self.aliases
        elif type == Unit.slot:
            def_list = self.slots
        elif type == Unit.intent:
            def_list = self.intents
        else:
            raise ValueError("Tried to get a definition with wrong type (expected"+
                             "alias, slot or intent)")

        if def_name not in def_list:
            type_str = "alias"
            if type == Unit.slot:
                type_str = "slot"
            elif type == Unit.intent:
                type_str = "intent"
            raise ValueError("Couldn't find a definition for "+type_str+" '"+
                              def_name+"'")

        return def_list[def_name]


    #=========== Util methods =================
    def check_indentation(self, indentation_nb, line, stripped_line):
        """
        Given the indentation of the previous line,
        checks the indentation of the line is correct (raises a `SyntaxError`
        otherwise) and returns the number of spaces its indented with.
        If this is the first line (`indentation_nb` is `None`),
        considers the indentation correct and returns the number of spaces
        the line is indented with.
        """
        current_indentation_nb = len(line) - len(stripped_line)
        if indentation_nb is None:
            return current_indentation_nb
        else:
            if current_indentation_nb == indentation_nb:
                return current_indentation_nb
            else:
                raise SyntaxError("Incorrect indentation",
                    (self.in_file.name, self.line_nb, indentation_nb, line))

    def get_top_level_line_type(self, line, stripped_line):
        """
        Returns the type of a top-level line (Note: this is expected to never
        be called for something else than a top-level line).
        Raises an error if the top-level line is not valid
        """
        if stripped_line == "":
            return LineType.empty
        elif stripped_line.startswith(COMMENT_SYM):
            return LineType.comment
        elif line.startswith(ALIAS_SYM):
            return LineType.alias_declaration
        elif line.startswith(SLOT_SYM):
            return LineType.slot_declaration
        elif line.startswith(INTENT_SYM):
            return LineType.intent_declaration
        elif line.startswith(INCLUDE_FILE_SYM):
            return LineType.include_file
        else:
            SyntaxError("Invalid syntax",
                (self.in_file.name, self.line_nb, 1, line))

    def split_contents(self, text, accept_slot_val=False):
        """
        Splits `text` into a list of `RuleContent`s (thus, only used on rules and
        not on defintions).
        If `accept_slot_val` is `True`, expressions after a `=` will be considered
        to be the slot value name for the splitted expression. In this case, the
        return value will be `(alt_name, list)`.
        """
        # Split string in list of words and raw units (as strings)
        words_and_units_raw = []
        current = ""

        escaped = False
        inside_choice = False
        must_parse_alt_slot_val = False
        for c in text:
            # Manage escapement
            if escaped:
                current += c
                escaped = False
                continue
            elif c == COMMENT_SYM:
                break
            elif inside_choice:
                if c == CHOICE_CLOSE_SYM:
                    words_and_units_raw.append(current+c)
                    current = ""
                    inside_choice = False
                else:
                    current += c
            elif c == ESCAPE_SYM:
                escaped = True
                current += c
            elif c.isspace():
                if not is_unit_start(current) and not is_choice(current):  # End of word
                    if current != "":
                        words_and_units_raw.append(current)
                    words_and_units_raw.append(' ')
                    current = ""
                elif current == "" and \
                    len(words_and_units_raw) > 0 and words_and_units_raw[-1] == ' ':
                        continue  # Double space in-between words
                else:
                    current += c
            elif c == UNIT_CLOSE_SYM:
                if is_unit_start(current):
                    words_and_units_raw.append(current+c)
                    current = ""
                else:
                    warnings.warn("Inconsistent use of the unit close symbol ("+
                        UNIT_CLOSE_SYM+") at line "+str(self.line_nb)+" of file '"+
                        self.in_file.name+"'. Consider escaping them if they are "+
                        "not supposed to close a unit.\nThe generation will "+
                        "however continue, considering it as a normal character.")
                    current += c
            elif c == CHOICE_CLOSE_SYM:
                warnings.warn("Inconsistent use of the choice close symbol ("+
                    CHOICE_CLOSE_SYM+") at line "+str(self.line_nb)+" of file '"+
                    self.in_file.name+"'. Consider escaping them if they are "+
                    "not supposed to close a unit.\nThe generation will "+
                    "however continue, considering it as a normal character.")
                current += c
            elif c == CHOICE_OPEN_SYM:
                if current != "":
                    words_and_units_raw.append(current)
                inside_choice = True
                current = c
            elif is_start_unit_sym(c) and current != ALIAS_SYM and \
                current != SLOT_SYM and current != INTENT_SYM:
                    if current != "":
                        words_and_units_raw.append(current)
                    current = c
            elif accept_slot_val and c == ALT_SLOT_VALUE_NAME_SYM:
                must_parse_alt_slot_val = True
                break
            else:  # Any other character
                current += c
        if current != "":
            words_and_units_raw.append(current)

        # Find the alternative slot value name if needed
        slot_val = None
        if must_parse_alt_slot_val:
            slot_val = \
                text[text.find(ALT_SLOT_VALUE_NAME_SYM):][1:].strip()

        # Make a list of `RuleContent`s from this parsing
        rules = []
        for (i, string) in enumerate(words_and_units_raw):
            if string == ' ':
                continue

            no_leading_space = (i == 0 or \
                (i != 0 and words_and_units_raw[i-1] != ' '))

            if is_word(string):
                rules.append(
                    WordRuleContent(remove_escapement(string), not no_leading_space)
                )

            unit_type = get_unit_type(string)
            if unit_type == Unit.word_group:
                (name, arg_value, variation, randgen, percentgen, casegen) = \
                    self.parse_unit(string)
                if name is None:
                    continue
                if arg_value is not None:
                    raise SyntaxError("Word groups cannot have an argument",
                        (self.in_file.name, self.line_nb, 0, name))
                if variation is not None:
                    raise SyntaxError("Word groups cannot have a variation",
                        (self.in_file.name, self.line_nb, 0, name))

                rules.append(
                    WordGroupRuleContent(remove_escapement(string),
                                  not no_leading_space, casegen=casegen,
                                  randgen=randgen, percentage_gen=percentgen)
                )
            elif unit_type == Unit.choice:
                choices = []
                print("choices not yet supported")
                continue
                rules.append(self.parse_choice(string))
            elif unit_type == Unit.alias:
                (name, arg_value, variation, randgen, percentgen, casegen) = \
                    self.parse_unit(string)
                if name is None:
                    raise SyntaxError("Aliases must have a name",
                        (self.in_file.name, self.line_nb, 0, name))

                rules.append(
                    AliasRuleContent(name, not no_leading_space, variation, arg_value,
                              casegen, randgen, percentgen, self)
                )
            elif unit_type == Unit.slot:
                (name, arg_value, variation, randgen, percentgen, casegen) = \
                    self.parse_unit(string)
                if name is None:
                    raise SyntaxError("Slots must have a name",
                        (self.in_file.name, self.line_nb, 0, name))

                rules.append(
                    SlotRuleContent(name, not no_leading_space, variation, arg_value,
                              casegen, randgen, percentgen, self)
                )
            else:  # Unit.intent
                (name, arg_value, variation, randgen, percentgen, casegen) = \
                    self.parse_unit(string)
                if name is None:
                    raise SyntaxError("Intents must have a name",
                        (self.in_file.name, self.line_nb, 0, name))

                rules.append(
                    IntentRuleContent(name, not no_leading_space, variation, arg_value,
                              casegen, randgen, percentgen, self)
                )

        if accept_slot_val:
            return (slot_val, rules)  # QUESTION: is it a problem to return two different things (defined by the arguments)?
        return rules


    def printDBG(self):
        print("\nAliases:")
        for name in self.aliases:
            current_alias_def = self.aliases[name]
            if "rules" in current_alias_def:  # No variations
                print("\t"+name+" (arg: "+str(current_alias_def["arg"])+"):")
                rules = current_alias_def["rules"]
                for rule in rules:
                    print("\t\trule: "+str(rule))
            else:  # Variations
                print("\t"+name+":")
                for variation in current_alias_def:
                    print("\t\tvariation: "+variation+" (arg: "+str(current_alias_def[variation]["arg"])+"):")
                    rules = current_alias_def[variation]["rules"]
                    for rule in rules:
                        print("\t\t\trule: "+str(rule))

        print("\nSlots:")
        for name in self.slots:
            current_slot_def = self.slots[name]
            if "rules" in current_slot_def:
                print("\t"+name+" (arg: "+str(current_slot_def["arg"])+"):")
                rules = current_slot_def["rules"]
                for rule in rules:
                    print("\t\trule: "+str(rule))
            else:
                print("\t"+name+": ")
                for variation in current_slot_def:
                    print("\t\tvariation: "+variation+" (arg: "+str(current_slot_def[variation]["arg"]+"):"))
                    rules = current_slot_def["rules"]
                    for rule in current_slot_def[variation]:
                        print("\t\t\trule: "+str(rule))

        print("\nIntents:")
        for name in self.intents:
            current_intent_def = self.intents[name]
            if "nb-gen-asked" in current_intent_def:
                    print("\t"+name+"(to generate "
                        +str(current_intent_def["nb-gen-asked"])+"x, arg: "+
                        str(current_intent_def["arg"])+"):")
                    for rule in current_intent_def["rules"]:
                        print("\t\trule: "+str(rule))
            else:
                print("\t"+name+":")
                for variation in current_intent_def:
                    current_variation = current_intent_def[variation]
                    print("\t\tvariation: "+variation+
                        " to generate "+str(current_variation["nb-gen-asked"])+
                        "x (arg: "+current_variation["arg"]+"):")
                    for rule in current_variation["rules"]:
                        print("\t\t\trule: "+str(rule))



if __name__ == "__main__":
    import warnings
    warnings.warn("You are running the wrong file ('Parser.py')." +
        "The file that should be run is 'main.py'.")
