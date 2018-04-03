import os
import argparse
import subprocess
import json
import urllib2
import csv
import time
import datetime
from threading import Timer


def clean_ending(file):
    while file[-1] == '\n' or file[-1] == '' or file[-1] == ' ':
        file.pop(-1)
    return file


# return number of different lines from answer
def compare_output(output, answer):
    diff = 0
    out_lines = clean_ending(output.read().splitlines())
    ans_lines = clean_ending(answer.read().splitlines())
    for i in range(0, min(len(ans_lines), len(out_lines))):
        if ans_lines[i] != out_lines[i]:
            diff = diff + 1
    if len(ans_lines) < len(out_lines):
        diff = diff + (len(out_lines) - len(ans_lines))
    return diff + max(len(ans_lines), len(out_lines)) - min(len(ans_lines), len(out_lines))


def run(cmd, in_filename=None, out_filename=None, timeout_sec=0):
    in_file = open(in_filename, 'r') if in_filename is not None else None
    out_file = open(out_filename, 'w') if out_filename is not None else None
    proc = subprocess.Popen(cmd, stdin=in_file, stdout=out_file)
    kill_proc = lambda p: p.kill()
    timer = Timer(timeout_sec, kill_proc, [proc])
    try:
        timer.start()
        return_code = proc.wait()
        return return_code
    finally:
        timer.cancel()


# parse argument
parser = argparse.ArgumentParser()
parser.add_argument("--name", help="set assignment name (ex. assign1)", type=str, required=True)
parser.add_argument("--repo_id", help="set repository id", type=str, required=True)
args = parser.parse_args()
if not args.name:
    print("set assignment name")
    exit(1)
if not args.repo_id:
    print("set repository id")
    exit(1)

# set directory vars
project_name = args.name
root_repo_id = args.repo_id
current_dir = os.getcwd()
graded_dir = "%s/graded/%s" % (current_dir, project_name)
testcases_dir = "%s/testcases/%s" % (current_dir, project_name)
# gitlab token
private_token = "7ZrthQvAHozC4sDaVs2e"

url = "https://gitlab.com/api/v4/projects/%s/forks?private_token=%s&per_page=100" % (root_repo_id, private_token)
data = json.load(urllib2.urlopen(url))

# read configuration file
conf_file_name = "%s/%s.json" % (testcases_dir, project_name)
configuration = json.load(open(conf_file_name))
if project_name != configuration["name"]:
    print("Configuration file is wrong")
    exit(1)

driver = configuration["driver"] == 'True'
test_number = int(configuration["test_number"])
valgrind = configuration["valgrind"][0] == 'True'
valgrind_test = int(configuration["valgrind"][1])
timelimit = int(configuration["timelimit"])
due_date = configuration["due_date"]
test_grade = (100 / test_number if not valgrind else 100 / (test_number + 1))

# all results
students_results = []

for meta in data:
    # setup git vars
    visibility = (1 if meta['visibility'] == "private" else 0)
    student_id = meta['owner']['username']
    student_id = student_id.replace("cs", "")
    last_activity = meta['last_activity_at']
    path = meta['path_with_namespace']
    student_git_url = "https://oauth2:%s@gitlab.com/%s.git" % (private_token, path)
    student_project_dir = "%s/%s" % (graded_dir, student_id)

    # setup grading vars
    student_total_grade = 0.0
    student_testcase_grade = 0.0
    student_comment = ''

    # clone
    os.system("rm -rf %s" % student_project_dir)
    os.system("git clone %s %s/" % (student_git_url, student_project_dir))


    # copy testcases and makefile
    os.system("cp %s/* %s/." % (testcases_dir, student_project_dir))

    # run makefile
    stat = run(["make", "-C" "%s/" % student_project_dir], timeout_sec=60)
    if stat != 0:
        student_comment += "| does not compile "
    else:
        # adding 5 points for compilable code
        student_total_grade += 5
        # start testing
        for i in range(1, test_number+1):
            # setup files
            test_output = "%s/output%d.txt" % (student_project_dir, i)
            test_input = "%s/input%d.txt" % (student_project_dir, i)
            user_output = "%s/user%d.txt" % (student_project_dir, i)
            run_command = (["%s/driver%d" % (student_project_dir, i)] if driver else ["%s/%s" % (student_project_dir, project_name)])
            # run
            stat = run(run_command, in_filename=test_input, out_filename=user_output, timeout_sec=timelimit*60)
            # check
            if stat == 0:
                diff = compare_output(open(user_output, 'r'), open(test_output, 'r'))
                if diff == 0:
                    student_testcase_grade += test_grade
                    student_comment += "| test%d-success " % i
                else:
                    student_comment += "| test%d-diff(%d) " % (i, diff)
            else:
                student_comment += "| test%d-crash " % i

        # test memory leak
        if valgrind:
            stat = run(["valgrind", "-v", "%s/driver%d" % (student_project_dir, valgrind_test)], out_file="valgrind.txt", timeout_sec=timelimit*60)
            if stat == 0:
                if 'no leak' in open('valgrind.txt'):
                    student_testcase_grade += test_grade
                    student_comment += "| no leak "
                else:
                    student_comment += "| memory leak "
            else:
                student_comment += "| valgrind run error "

    # checking if code is not empty, giving 5 points
    code_lines = sum(1 for line in open('%s/%s.cpp' %(student_project_dir, project_name)))
    if code_lines > 15:
        student_total_grade += 5
    # due date calc
    due_date_penalty = 0
    due_date_dt = datetime.datetime.strptime(due_date, '%Y-%m-%dT%H:%M:%S.%f')
    student_date_dt = datetime.datetime.strptime(last_activity, '%Y-%m-%dT%H:%M:%S.%fZ')
    delta = student_date_dt - due_date_dt
    if delta.days > 0 or delta.seconds > 0:
        if delta.days >= 3:
            due_date_penalty = 10
            student_comment += "| due date limit "
        else:
            due_date_penalty = 1 + delta.days
            student_comment += "| %d days due" % due_date_penalty

    # calc total grade
    student_total_grade += student_testcase_grade * 0.9
    student_total_grade = (1 - due_date_penalty * 0.1) * student_total_grade

    # add student's result to the list
    students_results.append([student_id, round(student_total_grade, 1), student_comment])

with open('%s/%s_grade.csv' % (graded_dir, project_name), 'wb') as out_file:
    wr = csv.writer(out_file, quoting=csv.QUOTE_ALL)
    wr.writerow(students_results)