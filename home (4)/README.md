# README

## How does your shell translate a line of input that a user enters into a command which is executed in the command line?

My shell takes the entire input line from the user and tokenizes it into individual commands and arguments using the shlex module. During this process, the shell identifies and handles pipe (|) operators, splitting the input into multiple subcommands. Each subcommand is executed in a separate child process, connected by pipes where the output of one command becomes the input for the next. Once all commands are executed, the final result is displayed on the standard output.

## What is the logic that your shell performs to find and substitute environment variables in user input? How does it handle the user escaping shell variables with a backslash (\) so that they are interpreted as literal strings?

When parsing the command string, my shell scans for the $ symbol to detect the use of environment variables. If it finds a valid environment variable, it substitutes it with its corresponding value. If the user escapes the $ symbol with a backslash (\), the shell treats it as a literal string rather than substituting the variable. This ensures that variables are handled properly when users want to include literal characters in the output.

## How does your shell handle pipelines as part of its execution? What logic in your program allows one command to read another command's stdout output as stdin?

My shell handles pipelines by recognizing the pipe (|) symbol during command parsing. When a pipe is detected, the shell creates child processes connected via pipes using os.pipe() and os.fork(). The output of one command is passed through the pipe and used as the input for the next command. This chaining of commands continues until the final command, whose output is displayed on the terminal. This allows commands to work together by passing data from one to the next.

## Test Structure

First and foremost, to ensure testing effectiveness, all tests should be run under the/home/tests entry with run_tests.sh!!!
In the/home/tests/io_files directory, I created various tests, including input/output (I/O) tests and end-to-end tests. These tests input commands through. in files and verify whether the output matches the expected results through. inspected files. In addition, I provided a script called tests/run_tests.sh that automatically runs all tests, which can determine whether the program has passed each test case and how many test cases have passed.
