#!/bin/bash

# Base directory for the tests and the shell script
TEST_DIR="/home/tests/io_files"
MYSH_SCRIPT="/home/mysh.py"
passed_tests=0
failed_tests=0
total_tests=0

# Test function
run_test() {
    test_name=$1
    input_file=$2
    expected_file=$3
    
    output=$(python3 $MYSH_SCRIPT < "$input_file" 2>&1)
    
    cleaned_output=$(echo "$output" | sed 's/^>> //g' | sed 's/>> //g')
    cleaned_output=$(echo "$cleaned_output" | sed -E 's/[ ]+[A-Z][a-z]{2}[ ]+[0-9]{1,2}[ ]+[0-9]{2}:[0-9]{2}//')

    cleaned_output=$(echo -e "$cleaned_output" | sed 's/\\t/\t/g' | sed 's/\\n/\n/g')

    if diff --strip-trailing-cr <(echo "$cleaned_output") "$expected_file" > /dev/null; then
        echo "$test_name: PASSED"
        echo "Expected:"
        cat "$expected_file"
        echo "Got:"
        echo "$cleaned_output"
        passed_tests=$((passed_tests + 1))
        total_tests=$((total_tests + 1))

    else
        echo "$test_name: FAILED"
        echo "Expected:"
        cat "$expected_file"
        echo "Got:"
        echo "$cleaned_output"
        failed_tests=$((failed_tests + 1))
        total_tests=$((total_tests + 1))
    fi
}

# Run all tests
run_test "Test echo_hello_world" "$TEST_DIR/echo_hello_world.in" "$TEST_DIR/echo_hello_world.expected"
run_test "Test basic_commands" "$TEST_DIR/basic_commands.in" "$TEST_DIR/basic_commands.expected"
run_test "Test var_command" "$TEST_DIR/var_command.in" "$TEST_DIR/var_command.expected"
run_test "Test cd_command" "$TEST_DIR/cd_command.in" "$TEST_DIR/cd_command.expected"
run_test "Test pipe_command" "$TEST_DIR/pipe_command.in" "$TEST_DIR/pipe_command.expected"
run_test "Test exit_command" "$TEST_DIR/exit_command.in" "$TEST_DIR/exit_command.expected"
run_test "Test pwd_error" "$TEST_DIR/pwd_error.in" "$TEST_DIR/pwd_error.expected"
run_test "Test which_command" "$TEST_DIR/which_command.in" "$TEST_DIR/which_command.expected"
run_test "Test multiple_commands" "$TEST_DIR/multiple_commands.in" "$TEST_DIR/multiple_commands.expected"
run_test "Test variable_expansion" "$TEST_DIR/variable_expansion.in" "$TEST_DIR/variable_expansion.expected"
run_test "Test mkdir_rmdir_command" "$TEST_DIR/mkdir_rmdir_command.in" "$TEST_DIR/mkdir_rmdir_command.expected"
run_test "Test chmod_command" "$TEST_DIR/chmod_command.in" "$TEST_DIR/chmod_command.expected"
echo "Passed $passed_tests out of $total_tests tests."
echo "Failed $failed_tests out of $total_tests tests."

