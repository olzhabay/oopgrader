# Student Assignment Grader

Script automatically retrieves students projects from their gitlab accounts that have been forked from original repository and grade them.

### Before using
Get user's private token https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html

Get project id, which is in the settings of the project


### How to use?
* Create new directory for semester, like 2018s, and place the script inside of directory.
* Place inside of directory `testcases` assignment's testcases with Makefile, input/output and json file.
* Input and output testcases must look like `input|number|.txt`, like **input1.txt** and **output1.txt**
* Json file must have same name as directory and have following setup:
```json
{
  "name" : "assign",                      # name of assignment
  "driver" : "False",                     # True if driver assignment, False if stdin
  "valgrind" : [ "False", "0" ],          # True if to use Valgrind, and driver number to run Valgrind
  "number" : "5",                         # Number of testcases or drivers
  "timelimit" : "5"                       # Time limit to run each testcase in sec
  "due_data" : "2018-03-30T20:00:00"      # Due date %Y-%m-%dT%H:%M:%S
}
```
* Run script with assignment name as argument, as `python script.py assign1`
* Results will be saved in same directory as script, in *.out file with assignment name (ex. assign1.out)
