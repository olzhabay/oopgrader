import os
import json
import glob
import sys
import difflib
import argparse
import pygit2
import subprocess
from pygit2 import Repository
from threading import Timer


class GitCallbacks(pygit2.RemoteCallbacks):
    def credentials(self, url, username_from_url, allowed_types):
        if allowed_types == pygit2.GIT_CREDTYPE_USERNAME:
            return pygit2.Username("git")
        elif allowed_types == pygit2.GIT_CREDTYPE_SSH_KEY:
            return pygit2.Keypair("git", "id_rsa.pub", "id_rsa", "")
        else:
            return None


# return without blank space ending
def clean_ending(file):
    while file[-1] == '\n' or file[-1] == '' or file[-1] == ' ':
        file.pop(-1)
    return file


# return number of different lines from answer
def compare_output(output, answer):
    diff = 0
    out_lines = clean_ending(output.splitlines())
    ans_lines = clean_ending(answer.splitlines())
    for i in range(0, len(ans_lines)):
        if ans_lines[i] != out_lines[i]:
            diff = diff + 1
    if len(ans_lines) < len(out_lines):
        diff = diff + (len(out_lines) - len(ans_lines))
    print diff
    return diff


def run(cmd, timeout_sec):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    kill_proc = lambda p: p.kill()
    timer = Timer(timeout_sec, kill_proc, [proc])
    try:
        timer.start()
        stdout, stderr = proc.communicate()
        return stderr, stdout
    finally:
        timer.cancel()
        return 1, "timeout"


# parse argument
parser = argparse.ArgumentParser()
parser.add_argument("--name", help="set assignment name (ex. assign1)", type=str, required=True)
args = parser.parse_args()
if not args.name:
    print("set assignment name")
    exit(1)

# set vars
project_name = args.name
current_dir = os.getcwd()
submission_dir = "%s/submissions" % current_dir
testcases_dir = "%s/testcases" % current_dir

# create dir
os.system("mkdir %s" % submission_dir)

student_list = [stud.rstrip() for stud in open("registration.txt")]
student_results = []

for student in student_list:
    grade = 0
    student_dir = "%s/%s" % (submission_dir, student)
    student_project_dir = "%s/%s" % (student_dir, project_name)
    os.system("mkdir %s" % student_dir)
    git_url = "ssh://gitlab.com/%s/%s" % (student, project_name)

    # clone repository if exists
    try:
        student_repo = pygit2.clone_repository(git_url, student_dir, callbacks=GitCallbacks)
    except:
        student_results.insert([student, grade, ["repo absent"]])
        continue

    # copy testcases and makefile
    os.system("cp %s/%s/* %s/." % (testcases_dir, project_name, student_project_dir))

    # run makefile
    (stat, output) = run("make -C %s" % student_project_dir, 30)
    if stat != 0:
        student_results.insert([student, grade, ["does not compile"]])
        continue

    # read configuration file
    conf_file_name = "%s/%s.json" % (student_project_dir, project_name)
    configuration = json.load(open(conf_file_name))
    if project_name != configuration["name"]:
        print("Configuration file is wrong")
        exit(1)
    driver = configuration["driver"]
    number = configuration["number"]
    valgrind = configuration["valgrind"][0]
    valgrind_test = configuration["valgrind"][1]
    timelimit = configuration["timelimit"]
    test_grade = 0
    if valgrind:
        test_grade = 100 / (number + valgrind)
    else:
        test_grade = 100 / number

    # start testing
    result_comment = ["test results: "]
    for i in range(0, number):
        if driver:
            (stat, output) = run("%s/driver%d" % (student_project_dir, i), timelimit)
        else:
            (stat, output) = run("%s/%s < input%d.txt" % (student_project_dir, project_name, i), timelimit)
        if stat == 0:
            diff = compare_output(output, open("%s/output%d.txt" % (student_project_dir, i), 'r'))
            if diff == 0:
                grade += test_grade
                result_comment.append("test%d")
            else:
                result_comment.append("test%d-diff(%d)" % (i, diff))
        else:
            result_comment.append("test%d-error(%s)" % (i, output))

    # test memory leak
    if valgrind:
        (stat, output) = run("valgrind -v %s/driver%d" % (student_project_dir, valgrind_test), timelimit)
        if 'no leak' in output:
            test_grade += test_grade
            result_comment.append("no leak")

    # add student's result to the list
    student_results.append([student, grade, result_comment])

# print result
print student_results
