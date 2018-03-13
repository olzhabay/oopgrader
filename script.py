import os
import sys
import argparse
import pygit2
from pygit2 import Repository

class GitCallbacks(pygit2.RemoteCallbacks):
    def credentials(self, url, username_from_url, allowed_types):
        if allowed_types == pygit2.GIT_CREDTYPE_USERNAME:
            return pygit2.Username("git")
        elif allowed_types == pygit2.GIT_CREDTYPE_SSH_KEY:
            return pygit2.Keypair("git", "id_rsa.pub", "id_rsa", "")
        else:
            return None

# parse argument
parser = argparse.ArgumentParser()
parser.add_argument("--name", help="set assignment name (ex. assign1)", type=str, required=True)
args = parser.parse_args()
if not args.name:
        print("set assignment name")
        exit(1)

# set vars
assignment = args.name
current_dir = os.getcwd()
submission_dir = "%s/submissions"%(current_dir)
testcases_dir = "%s/testcases"%(current_dir)

# create dir
os.system("mkdir %s",%(submission_dir))

student_list = [stud.rstrip() for stud in open("registration.txt")]

for student in student_list:
    student_dir = "%s/%s"%(submission_dir,student)
    os.system("mkdir %s",%(student_dir))
    git_repo = "ssh://gitlab.com/%s/%s"%(student, assignment)
    pygit2.clone_repository(git_repo, student_dir, callbacks=GitCallbacks)
    
