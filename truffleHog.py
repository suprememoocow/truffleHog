#!/usr/bin/env python
import shutil, sys, math, string, datetime, argparse, tempfile, os, fnmatch
from git import Repo
import json

if sys.version_info[0] == 2:
    reload(sys)  
    sys.setdefaultencoding('utf8')

BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
HEX_CHARS = "1234567890abcdefABCDEF"

file_filter_patterns = []

def pathfilter(path):
    for pat in file_filter_patterns:
        if ("/" in pat) or ("\\" in pat):
            if fnmatch.fnmatch(path, pat): return None
        else:
            if fnmatch.fnmatch(os.path.basename(path), pat): return None
    return path

def shannon_entropy(data, iterator):
    """
    Borrowed from http://blog.dkbza.org/2007/05/scanning-data-for-entropy-anomalies.html
    """
    if not data:
        return 0
    entropy = 0
    for x in (ord(c) for c in iterator):
        p_x = float(data.count(chr(x)))/len(data)
        if p_x > 0:
            entropy += - p_x*math.log(p_x, 2)
    return entropy


def get_strings_of_set(word, char_set, threshold=20):
    count = 0
    letters = ""
    strings = []
    for char in word:
        if char in char_set:
            letters += char
            count += 1
        else:
            if count > 20:
                strings.append(letters)
            letters = ""
            count = 0
    if count > threshold:
        strings.append(letters)
    return strings

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def find_strings(git_url, output):
    project_path = tempfile.mkdtemp()

    Repo.clone_from(git_url, project_path)

    repo = Repo(project_path)

    jsonOutput = output

    already_searched = set()
    for remote_branch in repo.remotes.origin.fetch():
        branch_name = str(remote_branch).split('/')[1]
        try:
            repo.git.checkout(remote_branch, b=branch_name)
        except:
            pass
     
        prev_commit = None
        for curr_commit in repo.iter_commits():
            if not prev_commit:
                pass
            else:
                #avoid searching the same diffs
                hashes = str(prev_commit) + str(curr_commit)
                if hashes in already_searched:
                    prev_commit = curr_commit
                    continue
                already_searched.add(hashes)
                diff = prev_commit.diff(curr_commit, create_patch=True)
                for blob in diff:
                    #print i.a_blob.data_stream.read()
                    if blob.a_path:
                        path = blob.a_path
                    else:
                        path = blob.b_path
                    if path:
                        if not pathfilter(path):
                            continue
                    printableDiff = blob.diff.decode()
                    if printableDiff.startswith("Binary files"):
                        continue
                    foundSomething = False
                    lines = blob.diff.decode().split("\n")
                    for line in lines:
                        for word in line.split():
                            base64_strings = get_strings_of_set(word, BASE64_CHARS)
                            hex_strings = get_strings_of_set(word, HEX_CHARS)
                            for string in base64_strings:
                                b64Entropy = shannon_entropy(string, BASE64_CHARS)
                                if b64Entropy > 4.5:
                                    foundSomething = True
                                    if jsonOutput:
                                        stringDiff = string
                                    else:
                                    printableDiff = printableDiff.replace(string, bcolors.WARNING + string + bcolors.ENDC)
                            for string in hex_strings:
                                hexEntropy = shannon_entropy(string, HEX_CHARS)
                                if hexEntropy > 3:
                                    foundSomething = True
                                    if jsonOutput:
                                        stringDiff = string
                                    else:
                                    printableDiff = printableDiff.replace(string, bcolors.WARNING + string + bcolors.ENDC)
                    if foundSomething:
                        commit_time =  datetime.datetime.fromtimestamp(prev_commit.committed_date).strftime('%Y-%m-%d %H:%M:%S')
                        if jsonOutput:
                            output = {}
                            output['file'] = str(path)
                            output['date'] = commit_time
                            output['branch'] = branch_name
                            output['commit'] = prev_commit.message
                            output['diff'] = printableDiff
                            output['string'] = stringDiff
                            print json.dumps(output)
                        else:
                            print(bcolors.OKGREEN + "File: " + str(path) + bcolors.ENDC)
                            print(bcolors.OKGREEN + "Date: " + commit_time + bcolors.ENDC)
                            print(bcolors.OKGREEN + "Branch: " + branch_name + bcolors.ENDC)
                            print(bcolors.OKGREEN + "Commit: " + prev_commit.message + bcolors.ENDC)
                            print(printableDiff)
                    
            prev_commit = curr_commit
    shutil.rmtree(project_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find secrets hidden in the depths of git.')
    parser.add_argument('--json', dest="output_json", action="store_true", help="Output in JSON")
    parser.add_argument('git_url', type=str, help='URL for secret searching')

    # if the .fileignore file exists, attempt to import file patterns
    try:
        with open('.fileignore', 'r') as f:
            for line in f:
                if not (line[0] == "#"):
                    file_filter_patterns.append(line.rstrip())
    except:
        pass

    args = parser.parse_args()
    find_strings(args.git_url, args.output_json)
