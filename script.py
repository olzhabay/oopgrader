import datetime
import json
import os
import subprocess
from argparse import ArgumentParser
from threading import Timer

import pandas

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
        # cleaning line from extra space in the end and compare
        ans_line = ans_lines[i].rstrip()
        out_line = out_lines[i].rstrip()
        if ans_line != out_line:
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
    :param timeout_sec: time limit in sec, after which command will be killed
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
    project_name = args.assign_name
    token = None
    if args.token_file:
        with open(args.token_file) as file:
            token = file.read().strip()
    individual = args.student

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
    extra_test = int(configuration["extra_test"])
    extra_test_pts = int(configuration["extra_test_points"])
    test_pts = (90 / test_number if not valgrind else 90 / (test_number + 1))

    # student list
    students_list = pandas.read_csv("%s/%s" % (current_dir, args.roster_file))
    columns = []
    columns.append("id")
    columns.append("submission")
    columns.append("compilation")
    for i in range(1, test_number + 1):
        columns.append("test%s" % i)
    if valgrind:
        columns.append("valgrind")
    if extra_test != 0:
        columns.append("test_extra")
    columns.append("due_date")
    columns.append("grade")
    results = []

    for index, student in students_list.iterrows():
        # if individual grading, skip others
        if individual is not None and str(student['id']).strip() != str(individual).strip():
            continue
        result = {'id': student['id']}
        grade = 0
        student_project_dir = "%s/%d" % (graded_dir, student['id'])
        student_git_url = "https://%s@github.com/%s/%s-%s.git" \
                          % (token, org_name, project_name, student['github_username'])

        # clone
        p = subprocess.Popen(['rm', '-rf', student_project_dir],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.communicate()
        p = subprocess.Popen(['git', 'clone', student_git_url, student_project_dir],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            print "  == clone failed with this output:"
            print "  == stdout:", out
            print "  == stderr:", err
            student['submission'] = "clone error"
        else:
            p = subprocess.Popen(['git', '--git-dir=%s/.git' % student_project_dir,
                                  'log', '-1', '--pretty=format:"%an"'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
            out = out.replace("\n", "")
            if out == "unistoopta":
                result['submission'] = "no submission"
            else:
                # successful submission
                result['submission'] = "success"
                grade += 5

                # copy testcases and makefile
                os.system("cp %s/* %s/." % (testcases_dir, student_project_dir))
                # run makefile
                stat = execute_command(["make", "-C" "%s/" % student_project_dir], timeout_sec=30)
                if stat != 0:
                    result['compilation'] = "do not compile"
                else:
                    # successful compilation
                    result['compilation'] = "success"
                    grade += 5

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
                        print "test %d" % i
                        # check
                        if stat == 0:
                            diff = compare_output(open(user_output, 'r'), open(test_output, 'r'))
                            if diff == 0:
                                result['test%s' % i] = "success"
                                grade += test_pts
                            else:
                                result['test%s' % i] = "difference in %s lines" % diff
                        else:
                            result['test%s' % i] = "crash"

                    # test memory leak
                    if valgrind:
                        stat = execute_command(["valgrind", 
                                                "--log-file=%s/valgrind.txt" % student_project_dir, 
                                                "%s/driver%d" % (student_project_dir, valgrind_test)],
                                               out_filename="%s/valgrind_out.txt" % student_project_dir, 
                                               timeout_sec=timelimit*60)
                        print "valgrind"
                        if stat == 0:
                            if 'no leaks' in open('%s/valgrind.txt' % student_project_dir).read():
                                result['valgrind'] = "success"
                                grade += test_pts
                            else:
                                result['valgrind'] = "leak"
                        else:
                            result['valgrind'] = "crash"

                    # extra point test
                    if extra_test != 0:
                        # setup files
                        test_output = "%s/output%d.txt" % (student_project_dir, extra_test)
                        test_input = "%s/input%d.txt" % (student_project_dir, extra_test)
                        user_output = "%s/user%d.txt" % (student_project_dir, extra_test)
                        run_command = (["%s/driver%d" % (student_project_dir, extra_test)] if driver else [
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
                                result['test_extra'] = "success"
                                grade += extra_test_pts
                            else:
                                result['test_extra'] = "difference in %s lines" % diff
                        else:
                            result['test_extra'] = "crash"

                    # calculate due date
                    p = subprocess.Popen(['git', '--git-dir=%s/.git' % student_project_dir,
                                          'log', '-1', '--format=%cd', '--date=iso'],
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
                    out, err = p.communicate()
                    out = out.replace("\n", "")
                    due_date_dt = datetime.datetime.strptime(due_date, "%Y-%m-%dT%H:%M:%S")
                    student_date_dt = datetime.datetime.strptime(out[:19], '%Y-%m-%d %H:%M:%S')
                    delta = student_date_dt - due_date_dt
                    if delta.days >= 0:
                        if delta.seconds > 60:
                            result['due_date'] = delta.days + 1
                        else:
                            result['due_date'] = delta.days
                    else:
                        result['due_date'] = 0

                    # calculate final grade
                    if result['due_date'] > 3:
                        grade = 0
                    else:
                        grade = grade * (1 - 0.1 * result['due_date'])

        result['grade'] = grade
        # append to results
        results.append(result)

    df = pandas.DataFrame(results, columns=columns)
    if individual is None:
        df.to_csv('%s/%s_grade.csv' % (current_dir, project_name), index=False)
    else:
        print df


if __name__ == '__main__':
    # parse argument
    parser = ArgumentParser(description="Download GitHub Classroom repositories for a given assignment")
    parser.add_argument('--org-name', help="Organization name for GitHub Classroom")
    parser.add_argument('--assign-name', help="Prefix string for the assignment.")
    parser.add_argument('--token-file', help="File containing GitHub authorization token/password.")
    parser.add_argument('--roster-file', help="CSV file containing classroom roster")
    parser.add_argument('--student', help="student id for individual grading")
    args = parser.parse_args()
    main(args)
