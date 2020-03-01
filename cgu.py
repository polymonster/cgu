# cgu - code gen utilities for parsing c-like languages for use in code generation tools
# copyright Alex Dixon 2020: https://github.com/polymonster/cgu/blob/master/license
import re
import json
import sys


# make code gen more readable and less fiddly
def in_quotes(string):
    return "\"" + string + "\""


# append to string with newline print() style
def src_line(line):
    line += "\n"
    return line


# like c style unsigned wraparound
def us(val):
    if val < 0:
        val = sys.maxsize + val
    return val


# remove all single and multi line comments
def remove_comments(source):
    lines = source.split("\n")
    inside_block = False
    conditioned = ""
    for line in lines:
        if inside_block:
            ecpos = line.find("*/")
            if ecpos != -1:
                inside_block = False
                line = line[ecpos+2:]
            else:
                continue
        cpos = line.find("//")
        mcpos = line.find("/*")
        if cpos != -1:
            conditioned += line[:cpos] + "\n"
        elif mcpos != -1:
            conditioned += line[:mcpos] + "\n"
            inside_block = True
        else:
            conditioned += line + "\n"
    return conditioned


# finds the end of a body of text enclosed between 2 symbols ie. [], {}, <>
def enclose(open_symbol, close_symbol, source, pos):
    pos = source.find(open_symbol, pos)
    stack = [open_symbol]
    pos += 1
    while len(stack) > 0 and pos < len(source):
        if source[pos] == open_symbol:
            stack.append(open_symbol)
        if source[pos] == close_symbol:
            stack.pop()
        pos += 1
    return pos


# parse a string and return the end position in source, taking into account escaped \" quotes
def enclose_string(start, source):
    pos = start+1
    while True:
        pos = source.find("\"", pos)
        prev = pos - 1
        if prev > 0:
            if source[prev] == "\\":
                pos = pos + 1
                continue
            return pos+1
    # un-terminated string
    print("ERROR: unterminated string")
    assert 0


# format source with indents
def format_source(source, indent_size):
    formatted = ""
    lines = source.splitlines()
    indent = 0
    indents = ["{"]
    unindnets = ["}"]
    newline = False
    for line in lines:
        if newline and len(line) > 0 and line[0] != "}":
            formatted += "\n"
        newline = False
        cur_indent = indent
        line = line.strip()
        attr = line.find("[[")
        if len(line) < 1 or attr != -1:
            continue
        for c in line:
            if c in indents:
                indent += 1
            elif c in unindnets:
                indent -= 1
                cur_indent = indent
                newline = True
        formatted += " " * cur_indent * indent_size
        formatted += line
        formatted += "\n"
    return formatted


# returns the name of a type.. ie struct <name>, enum <name>
def type_name(type_declaration):
    pos = type_declaration.find("{")
    name = type_declaration[:pos].strip().split()[1]
    return name


# tidy source with consistent spaces, remove tabs and comments to make subsequent operations easier
def sanitize_source(source):
    # replace tabs with spaces
    source = source.replace("\t", " ")
    # replace all spaces with single space
    source = re.sub(' +', ' ', source)
    # remove comments
    source = remove_comments(source)
    # remove empty lines and strip whitespace
    sanitized = ""
    for line in source.splitlines():
        line = line.strip()
        if len(line) > 0:
            sanitized += src_line(line)
    return sanitized


# finds token in source code
def find_token(token, source):
    delimiters = [
        "(", ")", "{", "}", ".", ",", "+", "-", "=", "*", "/",
        "&", "|", "~", "\n", "\t", "<", ">", "[", "]", ";", " "
    ]
    fp = source.find(token)
    if fp != -1:
        left = False
        right = False
        # check left
        if fp > 0:
            for d in delimiters:
                if source[fp - 1] == d:
                    left = True
                    break
        else:
            left = True
        # check right
        ep = fp + len(token)
        if fp < ep-1:
            for d in delimiters:
                if source[ep] == d:
                    right = True
                    break
        else:
            right = True
        if left and right:
            return fp
        # try again
        tt = find_token(token, source[fp + len(token):])
        if tt == -1:
            return -1
        return fp+len(token) + tt
    return -1


# replace all occurrences of token in source code
def replace_token(token, replace, source):
    while True:
        pos = find_token(token, source)
        if pos == -1:
            break
        else:
            source = source[:pos] + replace + source[pos + len(token):]
            pass
    return source


# find all occurences of token, with their location within source
def find_all_tokens(token, source):
    pos = 0
    locations = []
    while True:
        token_pos = find_token(token, source[pos:])
        if token_pos != -1:
            token_pos += pos
            locations.append(token_pos)
            pos = token_pos + len(token)
        else:
            break
    return locations


# find all string literals in source
def find_string_literals(source):
    pos = 0
    strings = []
    while True:
        pos = source.find("\"", pos)
        if pos == -1:
            break
        end = enclose_string(pos, source)
        string = source[pos:end]
        strings.append(string)
        pos = end+1
    return strings


# removes string literals and inserts a place holder, returning the ist of string literals and the conditioned source
def placeholder_string_literals(source):
    strings = find_string_literals(source)
    index = 0
    for s in strings:
        source = source.replace(s, '"<placeholder_string_literal_{}>"'.format(index))
        index += 1
    return strings, source


# replace placeholder literals with the strings
def replace_placeholder_string_literals(strings, source):
    index = 0
    for s in strings:
        source = source.replace('"<placeholder_string_literal_{}>"'.format(index), s)
        index += 1
    return source


# get all enum member names and values
def get_enum_members(declaration):
    start = declaration.find("{")+1
    end = enclose("{", "}", declaration, 0)-1
    body = declaration[start:end]
    members = body.split(",")
    conditioned = []
    for member in members:
        conditioned.append(member.strip())
    enum_value = 0
    enum_members = []
    for member in conditioned:
        if member.find("=") != -1:
            name_value = member.split("=")
            enum_members.append({
                "name": name_value[0],
                "value": name_value[1]
            })
        else:
            enum_members.append({
                "name": member,
                "value": enum_value
            })
            enum_value += 1
    return enum_members


# get all struct member names, types, defaults and other metadata
def get_struct_members(declaration):
    members = []
    pos = declaration.find("{")+1
    while pos != -1:
        end_pos = declaration.find(";", pos)
        if end_pos == -1:
            break
        bracket_pos = declaration.find("{", pos)
        start_pos = pos
        if bracket_pos < end_pos:
            end_pos = enclose("{", "}", declaration, start_pos)
        statement = declaration[start_pos:end_pos]
        member_type = "variable"
        if statement.find("(") != -1 and statement.find("=") == -1:
            member_type = "function"
        attrubutes = None
        attr_start = statement.find("[[")
        if attr_start != -1:
            attr_end = statement.find("]]")
            attrubutes = statement[attr_start+2:attr_end]
        members.append({
            "type": member_type,
            "declaration": statement,
            "attributes": attrubutes
        })
        pos = end_pos + 1
    return members


def get_members(type_specifier, declaration):
    lookup = {
        "enum": get_enum_members,
        "struct": get_struct_members
    }
    if type_specifier in lookup:
        return lookup[type_specifier](declaration)
    return []


# finds the fully qualified scope for a type declaration
def get_type_declaration_scope(source, type_pos):
    scope_identifier = [
        "namespace"
    ]
    pos = 0
    scopes = []
    while True:
        for i in scope_identifier:
            scope_start = source.find(i, pos)
            if scope_start != -1:
                scope_end = enclose("{", "}", source, scope_start)
                if scope_end > type_pos > scope_start:
                    scope_name = type_name(source[scope_start:scope_end])
                    scopes.append({
                        "type": i,
                        "name": scope_name
                    })
                    pos = source.find("{", scope_start) + 1
                else:
                    pos = scope_end
            else:
                return scopes
            if pos > type_pos:
                return scopes
    return []


# return list of any typedefs for a particular type
def find_typedefs(fully_qualified_name, source):
    pos = 0
    typedefs = []
    typedef_names = []
    while True:
        start_pos = find_token("typedef", source[pos:])
        if start_pos != -1:
            start_pos += pos
            end_pos = start_pos + source[start_pos:].find(";")
            typedef = source[start_pos:end_pos]
            q = find_token(fully_qualified_name, typedef)
            if q != -1:
                typedefs.append(source[start_pos:end_pos])
                name = typedef[q+len(fully_qualified_name):end_pos].strip()
                typedef_names.append(name)
            pos = end_pos
        else:
            break
    return typedefs, typedef_names


def find_type_attributes(source, type_pos):
    delimiters = [";", "}"]
    attr = source[:type_pos].rfind("[[")
    first_d = us(-1)
    for d in delimiters:
        first_d = min(us(source[:type_pos].rfind(d)), first_d)
    if first_d == us(-1):
        first_d = -1
    if attr > first_d:
        attr_end = source[attr:].find("]]")
        return source[attr+2:attr+attr_end]
    return None


# finds all type declarations.. ie struct, enum. returning them in dict with name, and code
def find_type_declarations(type_specifier, source):
    results = []
    names = []
    pos = 0
    while True:
        start_pos = find_token(type_specifier, source[pos:])
        if start_pos != -1:
            start_pos += pos
            end_pos = enclose("{", "}", source, start_pos)
            declaration = source[start_pos:end_pos]
            members = get_members(type_specifier, declaration)
            scope = get_type_declaration_scope(source, start_pos)
            name = type_name(declaration)
            qualified_name = ""
            for s in scope:
                if s["type"] == "namespace":
                    qualified_name += s["name"] + "::"
            qualified_name += name
            typedefs, typedef_names = find_typedefs(qualified_name, source)
            attributes = find_type_attributes(source, start_pos)
            results.append({
                "type": type_specifier,
                "name": name,
                "qualified_name": qualified_name,
                "declaration": declaration,
                "members": members,
                "scope": scope,
                "typedefs": typedefs,
                "typedef_names": typedef_names,
                "attributes": attributes
            })
            pos = end_pos+1
        else:
            break
    for r in results:
        names.append(r["name"])
        names.append(r["qualified_name"])
        for name in r["typedef_names"]:
            names.append(name)
    return results, names


# find include statements
def find_include_statements(source):
    includes = []
    for line in source.splitlines():
        if line.strip().startswith("#include"):
            includes.append(line)
    return includes


# main function for scope
def test():
    # read source from file
    source = open("test.h", "r").read()

    # sanitize source to make further ops simpler
    source = sanitize_source(source)
    print("--------------------------------------------------------------------------------")
    print("sanitize source ----------------------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    print(source)

    # find all include statements, fromsanitized source to ignore commented out ones
    includes = find_include_statements(source)
    print("--------------------------------------------------------------------------------")
    print("find includes ------------------------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    print(includes)

    # find string literals within source
    print("--------------------------------------------------------------------------------")
    print("find strings literals ----------------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    strings = find_string_literals(source)
    print(strings)

    # remove string literals to avoid conflicts when parsing
    print("--------------------------------------------------------------------------------")
    print("placeholder literals -----------------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    strings, source = placeholder_string_literals(source)
    print(format_source(source, 4))

    # find single token
    print("--------------------------------------------------------------------------------")
    print("find token ---------------------------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    token = "SOME_TOKEN"
    token_pos = find_token(token, source)
    print("token pos: {}".format(token_pos))
    print("token:" + source[token_pos:token_pos+len(token)])

    print("--------------------------------------------------------------------------------")
    print("find all tokens ----------------------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    token = "int"
    token_locations = find_all_tokens(token, source)
    for loc in token_locations:
        print("{}: ".format(loc) + source[loc:loc+10] + "...")

    # find structs
    print("--------------------------------------------------------------------------------")
    print("find structs -------------------------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    structs, struct_names = find_type_declarations("struct", source)
    print(struct_names)
    print(json.dumps(structs, indent=4))

    # find enums
    print("--------------------------------------------------------------------------------")
    print("find enums ---------------------------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    enums, enum_names = find_type_declarations("enum", source)
    print(enum_names)
    print(json.dumps(enums, indent=4))

    # replace placeholder literals
    print("--------------------------------------------------------------------------------")
    print("replace placeholder literals ---------------------------------------------------")
    print("--------------------------------------------------------------------------------")
    source = replace_placeholder_string_literals(strings, source)
    print(format_source(source, 4))


# entry
if __name__ == "__main__":
    test()
