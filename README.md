# Student Assignment Grader

Script automatically retrieves students projects from github classroom organization and grades them.

### Before using
Get private token https://help.github.com/articles/creating-a-personal-access-token-for-the-command-line/


### How to use?
* Create new directory for semester, like 2018s, and place the script inside of directory.
* Place inside of directory `testcases` assignment's testcases with Makefile, input/output and json file.
* Input and output testcases must look like `input|number|.txt`, like **input1.txt** and **output1.txt**
* Makefile should create executable same as assignment name in configuration, if it is not driver assignment.
If driver assignment, simply name executables as `driver|numner|`, like **driver1**
* Json file must have same name as directory and have following setup:
```json
{
  "name" : "assign",                      # name of assignment
  "driver" : "False",                     # True if driver assignment, False if stdin
  "valgrind" : [ "False", "0" ],          # True if to use Valgrind, and driver number to run Valgrind
  "number" : "5",                         # Number of testcases or drivers
  "timelimit" : "5"                       # Time limit to run each testcase in sec
  "due_data" : "2018-03-30T20:00:00"      # Due date %Y-%m-%dT%H:%M:%S
  "extra_test": "0",                      # Test number for extra points, or 0 if no extra test
  "extra_test_points": "0"                # Points to be given, if extra test passes
}
```
* Edit in *run.sh* script following information: github classroom organization name, assignment name, token file name,
class roster file name
* Results will be saved in same directory as script, in *.out file with assignment name (ex. assign_name.out)
* For an assignment testcase arrangement, you can see an example of `testcases/test_assign` directory
