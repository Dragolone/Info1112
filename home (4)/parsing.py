import re
import shlex
import os
import sys
import json

_PIPE_REGEX_PATTERN = re.compile(
    r"\\\""     # Match escaped double quotes
    r"|\\'"     # OR match escaped single quotes
    r"|\"(?:\\\"|[^\"])*\""  # OR match strings in double quotes
    r"|'(?:\\'|[^'])*'"      # OR match strings in single quotes
    r"|(\|)"    # Match unquoted pipe operator and capture
)

def split_by_pipe_op(cmd_str: str) -> list[str]:
    """
    Splits the command string by unquoted pipe operators.
    """
    split_str_indexes = []

    for match in _PIPE_REGEX_PATTERN.finditer(cmd_str):
        if match.group(1) is not None:
            split_str_indexes.append(match.start())

    if not split_str_indexes:
        return [cmd_str]

    split_str = []
    prev_index = 0
    for next_index in split_str_indexes:
        cmd_str_slice = cmd_str[prev_index:next_index]
        split_str.append(cmd_str_slice)
        prev_index = next_index + 1

    cmd_str_slice = cmd_str[prev_index:]
    split_str.append(cmd_str_slice)

    return split_str

def parse_myshrc(env_vars):
    """
    Parses the .myshrc file to set environment variables.
    """
    myshrc_path = os.path.expanduser("~/.myshrc")
    if os.getenv("MYSHDOTDIR"):
        myshrc_path = os.path.join(os.getenv("MYSHDOTDIR"), ".myshrc")
    
    if os.path.exists(myshrc_path):
        try:
            with open(myshrc_path, "r") as f:
                data = json.load(f)
                for key, value in data.items():
                    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key):
                        print(f"mysh: .myshrc: {key}: invalid characters for variable name", file=sys.stderr)
                    elif not isinstance(value, str):
                        print(f"mysh: .myshrc: {key}: not a string", file=sys.stderr)
                    else:
                        expanded_value = os.path.expandvars(value)
                        os.environ[key] = expanded_value
                        env_vars[key] = expanded_value
        except json.JSONDecodeError:
            print("mysh: invalid JSON format for .myshrc", file=sys.stderr)
    
    if "PROMPT" not in os.environ:
        os.environ["PROMPT"] = ">> "
    if "MYSH_VERSION" not in os.environ:
        os.environ["MYSH_VERSION"] = "1.0"
    if "PATH" not in os.environ:
        os.environ["PATH"] = os.defpath

def parse_command(command_str: str) -> list[str]:
    """
    Parses a command string into a list of arguments.
    """
    return shlex.split(command_str, posix=True)

def expand_variables(cmd_str: str) -> str:
    result = []
    escaped = False
    in_single_quote = False
    in_double_quote = False

    i = 0
    while i < len(cmd_str):
        char = cmd_str[i]

        if escaped:
            result.append(char)
            escaped = False

        elif char == '\\':
            escaped = True

        elif char == "'":
            in_single_quote = not in_single_quote
            result.append(char)

        elif char == '"':
            in_double_quote = not in_double_quote
            result.append(char)

        elif char == '$' and i + 1 < len(cmd_str) and cmd_str[i + 1] == '{':
            end_brace_index = cmd_str.find('}', i + 2)
            if end_brace_index != -1:
                var_name = cmd_str[i+2:end_brace_index]
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                    print(f"mysh: syntax error: invalid characters for variable {var_name}", file=sys.stderr)
                    return None
                var_value = os.environ.get(var_name, '')
                result.append(var_value)
                i = end_brace_index
            else:
                result.append(char)
        
        else:
            result.append(char)
        i += 1

    expanded_cmd_str = ''.join(result)
    return expanded_cmd_str.replace('~', '/home', 1)

    
def handle_syntax_errors(cmd_str: str) -> bool:
    """
    Checks for syntax errors in the command string, specifically handling nested quotes.
    """
    in_single_quote = False
    in_double_quote = False

    for char in cmd_str:
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

    if in_single_quote or in_double_quote:
        print("mysh: syntax error: unterminated quote", file=sys.stderr)
        return True
    
    return False


