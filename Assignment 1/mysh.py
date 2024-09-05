import os
import shlex
import sys
import re
import signal
import json
from parsing import parse_myshrc, split_by_pipe_op, parse_command, expand_variables, handle_syntax_errors

BUILTIN_COMMANDS = ["exit", "pwd", "cd", "var", "which"]

def setup_signals():
    signal.signal(signal.SIGTTIN, signal.SIG_IGN)
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def setup_signals_pipe():
    signal.signal(signal.SIGTTIN, signal.SIG_IGN)
    signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal_handler)

def signal_handler(sig, frame):
    pgid = os.getpgid(0)
    os.killpg(pgid, signal.SIGINT)

def parse_command_expanded(command_str):
    command_strs = shlex.shlex(command_str.replace('\\$', '\\\\$'), posix=True)
    command_strs.whitespace_split = True
    command_strs.escapedquotes = '"' + "'"
    command_strs = list(command_strs)
    command_strs = [expand_variables(cmd) for cmd in command_strs]
    return command_strs

def handle_builtin(command, args):
    if command == "exit":
        if len(args) > 2:
            print("exit: too many arguments", file=sys.stderr)
        elif len(args) == 2:
            try:
                exit_code = int(args[1])
                sys.exit(exit_code)
            except ValueError:
                print(f"exit: non-integer exit code provided: {args[1]}", file=sys.stderr)
        else:
            sys.exit(0)
        return True

    elif command == "pwd":
        if len(args) > 2:
            print(f"pwd: invalid option: {args[1]}", file=sys.stderr)
        elif len(args) == 2:
            if args[1] == "-P":
                print(os.path.realpath(os.environ.get("PWD", os.getcwd())))
            else:
                for option in args[1][1:]:
                    if option != 'P':
                        print(f"pwd: invalid option: -{option}", file=sys.stderr)
                        break  
        elif len(args) == 1:
            print(os.environ.get("PWD", os.getcwd()))
        return True

    elif command == "cd":
        if len(args) > 2:
            print("cd: too many arguments", file=sys.stderr)
        elif len(args) == 1:
            os.chdir(os.path.expanduser("~"))
            os.environ["PWD"] = os.path.expanduser("~")
        else:
            path = os.path.expanduser(args[1])
            try:
                if path == "..":
                    os.chdir(path)
                    os.environ["PWD"] = os.path.dirname(os.environ["PWD"])
                else:
                    os.chdir(path)
                    if os.path.isabs(path):
                        os.environ["PWD"] = os.path.realpath(path) if "-P" in args else path
                    else:
                        new_path = os.path.normpath(os.path.join(os.environ["PWD"], path))
                        os.environ["PWD"] = os.path.realpath(new_path) if "-P" in args else new_path
            except FileNotFoundError:
                print(f"cd: no such file or directory: {path}", file=sys.stderr)
            except NotADirectoryError:
                print(f"cd: not a directory: {path}", file=sys.stderr)
            except PermissionError:
                print(f"cd: permission denied: {path}", file=sys.stderr)
        return True

    elif command == "var":
        if args[1].startswith('-'):
            for option in args[1][1:]:
                if option != 's':  
                    print(f"var: invalid option: -{option}", file=sys.stderr)
                    return True
        
        if args[1] == '-s':
            if len(args) != 4:
                print(f"var: expected 3 arguments with -s, got {len(args) - 1}", file=sys.stderr)
                return True
            
            var_name = args[2]
            command_str = args[3]
            command_str = command_str.replace('~', '/home', 1) 

            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                print(f"var: invalid characters for variable {var_name}", file=sys.stderr)
                return True

            try:
                command_output = execute_command_and_capture_output(command_str)
                os.environ[var_name] = command_output  
            except Exception as e:
                print(f"var: command failed with error: {e}", file=sys.stderr)
                return True

        else:
            if len(args) != 3:
                print(f"var: expected 2 arguments, got {len(args) - 1}", file=sys.stderr)
                return True
            var_name = args[1]
            var_value = args[2]

            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                print(f"var: invalid characters for variable {var_name}", file=sys.stderr)
                return True

            os.environ[var_name] = var_value

        return True

    
    elif command == "which":
        if len(args) < 2:
            print("usage: which command ...", file=sys.stderr)
            return True

        for cmd in args[1:]:
            if cmd in BUILTIN_COMMANDS:
                print(f"{cmd}: shell built-in command")
            else:
                cmd_path = search_cmd_path(cmd)

                if cmd_path and os.access(cmd_path, os.X_OK):
                    print(cmd_path)
                else:
                    print(f"{cmd} not found")
        return True


    else:
        return False


def search_cmd_path(cmd):
    cmd_path = None
    for path_dir in os.environ.get('PATH', '').split(os.pathsep):
        possible_path = os.path.join(path_dir, cmd)
        if os.path.exists(possible_path):
            cmd_path = possible_path
            break
    if not cmd_path:
        if os.path.exists(cmd):
            cmd_path = os.path.abspath(cmd)
    return cmd_path

def execute_pipeline(pipeline):
    processes = []
    prev_pipe_read = None

    for command in pipeline:
        if len(command.strip()) == 0:
            print("mysh: syntax error: expected command after pipe", file=sys.stderr)
            return
    for command in pipeline:
        cmd = command.split()[0]
        if cmd not in BUILTIN_COMMANDS:
            cmd_path = search_cmd_path(cmd)
            if not cmd_path:
                print(f"mysh: command not found: {cmd}", file=sys.stderr)
                return
            if not os.access(cmd_path, os.X_OK):
                print(f"mysh: permission denied: {cmd}", file=sys.stderr)
                return

    for i, command in enumerate(pipeline):
        command = command.replace('~', '/home') 
        args = parse_command_expanded(command)
        if i == 0:
            if len(pipeline) == 1:
                if not handle_builtin(args[0], args):
                    pid = os.fork()
                    if pid == 0:
                        signal.signal(signal.SIGINT, signal.SIG_DFL)
                        os.setpgid(0, 0)
                        os.execvpe(args[0], args, os.environ)
                    else:
                        os.setpgid(pid, pid)
                        os.wait()
            else:
                pipe_read, pipe_write = os.pipe()
                pid = os.fork()
                if pid == 0:
                    signal.signal(signal.SIGINT, signal.SIG_DFL)
                    os.setpgid(0, 0)
                    os.dup2(pipe_write, 1)
                    os.close(pipe_read)
                    os.execvpe(args[0], args, os.environ)
                else:
                    os.setpgid(pid, pid)
                    processes.append(pid)
                    os.close(pipe_write)
                    prev_pipe_read = pipe_read
        else:
            pipe_read, pipe_write = os.pipe() if i < len(pipeline) - 1 else (None, None)
            pid = os.fork()
            if pid == 0:
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                os.setpgid(0, 0)
                os.dup2(prev_pipe_read, 0)
                if pipe_write is not None:
                    os.dup2(pipe_write, 1)
                os.close(prev_pipe_read)
                if pipe_write is not None:
                    os.close(pipe_write)
                os.execvpe(args[0], args, os.environ)
            else:
                os.setpgid(pid, pid)
                processes.append(pid)
                os.close(prev_pipe_read)
                if pipe_write is not None:
                    os.close(pipe_write)
                prev_pipe_read = pipe_read

    for pid in processes:
        os.waitpid(pid, 0)

def execute_pipeline_command_and_capture_output(pipeline):
    processes = []
    prev_pipe_read = None
    output = ""

    for i, command in enumerate(pipeline):
        command = command.replace('~', '/home') 
        args = parse_command_expanded(command)
        if i == 0:
            if len(pipeline) == 1:
                if not handle_builtin(args[0], args):
                    pid = os.fork()
                    if pid == 0:
                        # default signal handler for SIGINT
                        signal.signal(signal.SIGINT, signal.SIG_DFL)
                        os.setpgid(0, 0)
                        os.execvpe(args[0], args, os.environ)
                    else:
                        os.setpgid(pid, pid)
                        os.wait()
            else:
                pipe_read, pipe_write = os.pipe()
                pid = os.fork()
                if pid == 0:
                    # default signal handler for SIGINT
                    signal.signal(signal.SIGINT, signal.SIG_DFL)
                    os.setpgid(0, 0)
                    os.dup2(pipe_write, 1)
                    os.close(pipe_read)
                    os.execvpe(args[0], args, os.environ)
                else:
                    os.setpgid(pid, pid)
                    processes.append(pid)
                    os.close(pipe_write)
                    prev_pipe_read = pipe_read
        elif i == len(pipeline) - 1:
            pipe_read, pipe_write = os.pipe()
            pid = os.fork()
            if pid == 0:
                # default signal handler for SIGINT
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                os.setpgid(0, 0)
                os.dup2(prev_pipe_read, 0)
                os.dup2(pipe_write, 1)
                os.close(prev_pipe_read)
                os.close(pipe_write)
                os.execvpe(args[0], args, os.environ)
            else:
                os.setpgid(pid, pid)
                processes.append(pid)
                # read from the last pipe
                os.close(pipe_write)
                with os.fdopen(pipe_read, 'r') as pipe:
                    output = pipe.read()
        else:
            pipe_read, pipe_write = os.pipe() if i < len(pipeline) - 1 else (None, None)
            pid = os.fork()
            if pid == 0:
                # default signal handler for SIGINT
                signal.signal(signal.SIGINT, signal.SIG_DFL)
                os.setpgid(0, 0)
                os.dup2(prev_pipe_read, 0)
                if pipe_write is not None:
                    os.dup2(pipe_write, 1)
                os.close(prev_pipe_read)
                if pipe_write is not None:
                    os.close(pipe_write)
                os.execvpe(args[0], args, os.environ)
            else:
                os.setpgid(pid, pid)
                processes.append(pid)
                os.close(prev_pipe_read)
                if pipe_write is not None:
                    os.close(pipe_write)
                prev_pipe_read = pipe_read
    for pid in processes:
        os.waitpid(pid, 0)
    return output

def execute_command_and_capture_output(command):
    if '|' in command:
        pipeline = split_by_pipe_op(command)
        return execute_pipeline_command_and_capture_output(pipeline)
    args = parse_command_expanded(command)
    pipe_read, pipe_write = os.pipe()

    if args[0] not in BUILTIN_COMMANDS and not search_cmd_path(args[0]):
        cmd_path = search_cmd_path(args[0])
        if not cmd_path:
            print(f"mysh: command not found: {args[0]}", file=sys.stderr)
            return ""
        if not os.access(cmd_path, os.X_OK):
            print(f"mysh: permission denied: {args[0]}", file=sys.stderr)
            return ""

    pid = os.fork()
    if pid == 0:
        # default signal handler for SIGINT
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            os.setpgid(0, 0)
        except Exception:
            pass

        os.dup2(pipe_write, 1)
        os.close(pipe_read)
        try:
            os.execvpe(args[0], args, os.environ)
        except PermissionError:
            os.write(pipe_write, f"mysh: permission denied: {args[0]}\n".encode())
            sys.exit(1)
        except Exception as e:
            os.write(pipe_write, f"mysh: error: {e}\n".encode())
            sys.exit(1)
    else:
        try:
            os.setpgid(pid, pid)
        except Exception:
            pass
        except Exception as e:
            print(f"mysh: error: {e}", file=sys.stderr)

        os.close(pipe_write)
        os.waitpid(pid, 0)

    with os.fdopen(pipe_read, 'r') as pipe:
        output = pipe.read()
        if args[0] != 'cat':
            output = output.rstrip()

    return output


def main():
    setup_signals()

    env_vars = {}
    parse_myshrc(env_vars)  
    
    while True:
        try:
            user_input = input(os.getenv('PROMPT', '>> '))
            if not user_input.strip():
                continue

            try:
                pipeline = split_by_pipe_op(user_input)
                error = False
                for command in pipeline:
                    command_strs = shlex.shlex(command, posix=True)
                    command_strs.whitespace_split = True
                    command_strs.escapedquotes = '"' + "'"
                    command_strs = list(command_strs)
                    for command_str in command_strs:
                        if expand_variables(command_str) == None:
                            error = True
                            break
                    if error:
                        break
                if error:
                    continue
            except Exception:
                print("mysh: syntax error: unterminated quote", file=sys.stderr)
                continue

            pipeline = split_by_pipe_op(user_input)

            if len(pipeline) > 1:
                setup_signals_pipe()
                execute_pipeline(pipeline)
                setup_signals()
            else:
                args = parse_command_expanded(user_input)
                if not handle_builtin(args[0], args):
                    cmd_path = search_cmd_path(args[0])
                    if not cmd_path:
                        print(f"mysh: command not found: {args[0]}", file=sys.stderr)
                    elif not os.access(cmd_path, os.X_OK):
                        print(f"mysh: permission denied: {args[0]}", file=sys.stderr)
                    else:
                        pid = os.fork()
                        if pid == 0:
                            # default signal handler for SIGINT
                            signal.signal(signal.SIGINT, signal.SIG_DFL)
                            os.setpgid(0, 0)
                            os.execvpe(args[0], args, os.environ)
                        else:
                            try:
                                os.setpgid(pid, pid)
                            except Exception:
                                pass
                            pgid = os.getpgid(pid)
                            terminal = os.open('/dev/tty', os.O_RDWR)
                            os.tcsetpgrp(terminal, pgid)
                            os.wait()
                            pgrp = os.getpgrp()
                            os.tcsetpgrp(terminal, pgrp)
                            os.close(terminal)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue
        except Exception as e:
            print(f"mysh: error: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    main()


