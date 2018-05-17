import os
import subprocess
import json
import urllib2
import csv
import requests
import re
import datetime
import pandas
from threading import Timer
from argparse import ArgumentParser

GRADING_TAG = '__graded_commit'
GRADING_BRANCH = '__grading_branch'


def clean_ending(lines):
    while len(lines) > 0 and (lines[-1] == '\n' or lines[-1] == '' or lines[-1] == ' '):
        lines.pop(-1)
    return lines


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


def execute_command(cmd, in_filename=None, out_filename=None, timeout_sec=0):
    """
    Runs command in subprocess in other thread and kills it if exceeds time limit.
    :param cmd: Command to run
    :param in_filename: Input file stream to feed command
    :param out_filename: Output file stream to which command prints
    :param timeout_sec:
    :return:
    """
    in_file = open(in_filename, 'r') if in_filename is not None else None
    out_file = open(out_filename, 'w') if out_filename is not None else None
    proc = subprocess.Popen(cmd, stdin=in_file, stdout=out_file)
    kill_proc = lambda p: p.kill()
    timer = Timer(timeout_sec, kill_proc, [proc])
    try:
        timer.start()
        proc.wait()
        var = proc.communicate()[0]
        return proc.returncode
    finally:
        timer.cancel()


def main(args):
    # vars
    org_name = args.org_name
    project_name = args.project_name
    token = None
    if args.token_file:
        with open(args.token_file) as file:
            token = file.read().strip()

    # set directory vars
    current_dir = os.getcwd()
    graded_dir = "%s/graded/%s" % (current_dir, project_name)
    testcases_dir = "%s/testcases/%s" % (current_dir, project_name)

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
    test_pts = (90 / test_number if not valgrind else 90 / (test_number + 1))

    # all results
    students_list = pandas.read_csv("%s/%s" % (current_dir, args.roster_file))
    students_list["submission"] = ""
    students_list["compilation"] = ""
    for i in range(1, test_number + 1):
        students_list["test%s" % 1] = ""
    if valgrind:
        students_list["valgrind"] = ""
    students_list['due_date'] = 0
    students_list['grade'] = 0.0

    for student in students_list:
        student_project_dir = "%s/%s" % (graded_dir, student['id'])
        student_git_url = "https://%s@github.com/%s/%s-%s.git" \
                          % (token, org_name, project_name, student['github_id'])

        # clone
        p = subprocess.Popen(['rm', '-rf', student_project_dir],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.communicate()
        p = subprocess.Popen(['git', 'cline', student_git_url, student_project_dir],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            print "  == clone failed with this output:"
            print "  == stdout:", out
            print "  == stderr:", err
            student['submission'] = "clone error"
            continue
        # successful submission
        student['submission'] = "success"
        student['grade'] += 5

        # copy testcases and makefile
        os.system("cp %s/* %s/." % (testcases_dir, student_project_dir))
        # run makefile
        stat = execute_command(["make", "-C" "%s/" % student_project_dir], timeout_sec=60)
        if stat != 0:
            student['compilation'] = "do not compile"
            continue
        # successful compilation
        student['compilation'] = "success"
        student['grade'] += 5

        # start testing
        for i in range(1, test_number + 1):

            # setup files
            test_output = "%s/output%d.txt" % (student_project_dir, i)
            test_input = "%s/input%d.txt" % (student_project_dir, i)
            user_output = "%s/user%d.txt" % (student_project_dir, i)
            run_command = (["%s/driver%d" % (student_project_dir, i)] if driver else [
                "%s/%s" % (student_project_dir, project_name)])

            # run test case
            stat = execute_command(run_command,
                                   in_filename=test_input,
                                   out_filename=user_output,
                                   timeout_sec=timelimit * 60)
            # check
            if stat == 0:
                diff = compare_output(open(user_output, 'r'), open(test_output, 'r'))
                if diff == 0:
                    student['test%s' % i] = "success"
                    student['grade'] += test_pts
                else:
                    student['test%s' % i] = "difference in %s lines" % diff
            else:
                student['test%s' % i] = "crash"

        # test memory leak
        if valgrind:
            stat = execute_command(["valgrind", "-v", "%s/driver%d" % (student_project_dir, valgrind_test)],
                                   out_filename="valgrind.txt", timeout_sec=timelimit*60)
            if stat == 0:
                if 'no leak' in open('valgrind.txt'):
                    student['valgrind'] = "success"
                    student['grade'] += test_pts
                else:
                    student['valgrind'] = "leak"
            else:
                student['valgrind'] = "crash"

        # calculate due date
        p = subprocess.Popen(['git', 'log', '-1', '--format=%cd', '%Y-%m-%dT%H:%M:%S'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        due_date_dt = datetime.datetime.strptime(due_date, "%Y-%m-%dT%H:%M:%S")
        student_date_dt = datetime.datetime.strptime(out, '%Y-%m-%dT%H:%M:%S')
        delta = student_date_dt - due_date_dt
        student['due_date'] = delta.days
        if delta.min > 0:
            student['due_date'] += 1

        # calculate final grade
        if student['due_date'] >= 3:
            student['grade'] = 10
        else:
            student['grade'] = 10 + (student['grade']-10) * (1 - 0.1 * student['due_date'])

    students_list.to_csv('%s/%s_grade.csv' % (graded_dir, project_name), sep=',')


if __name__ == '__main__':
    # parse argument
    parser = ArgumentParser(description="Download GitHub Classroom repositories for a given assignment")
    parser.add_argument('org_name', help="Organization name for GitHub Classroom")
    parser.add_argument('assign_name', help="Prefix string for the assignment.")
    parser.add_argument('-u', '--user', help="GitHub username.")
    parser.add_argument('-t', '--token-file', help="File containing GitHub authorization token/password.")
    parser.add_argument('-r', '--roster-file', help="CSV file containing classroom roster")
    args = parser.parse_args()
    main(args)
