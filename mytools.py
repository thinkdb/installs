__author__ = 'ruiayLinSunny'

"""
This module contains methods for working with mysql server tools.
"""

import inspect
import os
import re
import sys
import shutil
import socket
import subprocess
import time

from format import print_list
from exception import UtilError

PYTHON_MIN_VERSION = (2, 6, 0)
PYTHON_MAX_VERSION = (3, 0, 0)


def _add_basedir(search_paths, path_str):
    """Add a basedir and all known sub directories

    This method builds a list of possible paths for a basedir for locating
    special MySQL files like mysqld (mysqld.exe), etc.

    search_paths[inout] List of paths to append
    path_str[in]        The basedir path to append
    """
    search_paths.append(path_str)
    search_paths.append(os.path.join(path_str, "sql"))       # for source trees
    search_paths.append(os.path.join(path_str, "client"))    # for source trees
    search_paths.append(os.path.join(path_str, "share"))
    search_paths.append(os.path.join(path_str, "scripts"))
    search_paths.append(os.path.join(path_str, "bin"))
    search_paths.append(os.path.join(path_str, "libexec"))
    search_paths.append(os.path.join(path_str, "mysql"))


def get_tool_path(basedir, tool, fix_ext=True, required=True,
                  defaults_paths=None, search_PATH=False):
    """Search for a MySQL tool and return the full path

    basedir[in]         The initial basedir to search (from mysql server)
    tool[in]            The name of the tool to find
    fix_ext[in]         If True (default is True), add .exe if running on
                        Windows.
    required[in]        If True (default is True), and error will be
                        generated and the utility aborted if the tool is
                        not found.
    defaults_paths[in]  Default list of paths to search for the tool.
                        By default an empty list is assumed, i.e. [].
    search_PATH[in]     Boolean value that indicates if the paths specified by
                        the PATH environment variable will be used to search
                        for the tool. By default the PATH will not be searched,
                        i.e. search_PATH=False.
    Returns (string) full path to tool
    """
    if not defaults_paths:
        defaults_paths = []
    search_paths = []

    if basedir:
        # Add specified basedir path to search paths
        _add_basedir(search_paths, basedir)
    if defaults_paths and len(defaults_paths):
        # Add specified default paths to search paths
        for path in defaults_paths:
            search_paths.append(path)
    else:
        # Add default basedir paths to search paths
        _add_basedir(search_paths, "/usr/local/mysql/")
        _add_basedir(search_paths, "/usr/sbin/")
        _add_basedir(search_paths, "/usr/share/")

    # Search in path from the PATH environment variable
    if search_PATH:
        for path in os.environ['PATH'].split(os.pathsep):
            search_paths.append(path)

    if os.name == "nt" and fix_ext:
        tool = tool + ".exe"
    # Search for the tool
    print 'search_paths : ',search_paths
    for path in search_paths:
        norm_path = os.path.normpath(path)
        print 'norm_path : ' , norm_path
        if os.path.isdir(norm_path):
            toolpath = os.path.join(norm_path, tool)
            if os.path.isfile(toolpath):
                return toolpath
            else:
                if tool == "mysqld.exe":
                    toolpath = os.path.join(norm_path, "mysqld-nt.exe")
                    if os.path.isfile(toolpath):
                        return toolpath
    if required:
        raise UtilError("Cannot find location of %s." % tool)

    return None


def delete_directory(path):
    """Remove a directory (folder) and its contents.

    path[in]           target directory
    """
    if os.path.exists(path):
        # It can take up to 10 seconds for Windows to 'release' a directory
        # once a process has terminated. We wait...
        if os.name == "nt":
            stop = 10
            i = 1
            while i < stop and os.path.exists(path):
                shutil.rmtree(path, True)
                time.sleep(1)
                i += 1
        else:
            shutil.rmtree(path, True)


def execute_script(run_cmd, filename=None, options=None, verbosity=False):
    """Execute a script.

    This method spawns a subprocess to execute a script. If a file is
    specified, it will direct output to that file else it will suppress
    all output from the script.

    run_cmd[in]        command/script to execute
    filename[in]       file path name to file, os.stdout, etc.
                       Default is None (do not log/write output)
    options[in]        arguments for script
                       Default is no arguments ([])
    verbosity[in]      show result of script
                       Default is False

    Returns int - result from process execution
    """
    if options is None:
        options = []
    if verbosity:
        f_out = sys.stdout
    else:
        if not filename:
            filename = os.devnull
        f_out = open(filename, 'w')

    str_opts = [str(opt) for opt in options]
    cmd_opts = " ".join(str_opts)
    command = " ".join([run_cmd, cmd_opts])

    if verbosity:
        print("# SCRIPT EXECUTED: {0}".format(command))

    proc = subprocess.Popen(command, shell=True,
                            stdout=f_out, stderr=f_out)
    ret_val = proc.wait()
    if not verbosity:
        f_out.close()
    return ret_val


def ping_host(host, timeout):
    """Execute 'ping' against host to see if it is alive.

    host[in]           hostname or IP to ping
    timeout[in]        timeout in seconds to wait

    returns bool - True = host is reachable via ping
    """
    if sys.platform == "darwin":
        run_cmd = "ping -o -t %s %s" % (timeout, host)
    elif os.name == "posix":
        run_cmd = "ping -w %s %s" % (timeout, host)
    else:  # must be windows
        run_cmd = "ping -n %s %s" % (timeout, host)

    ret_val = execute_script(run_cmd)

    return (ret_val == 0)


def get_mysqld_version(mysqld_path):
    """Return the version number for a mysqld executable.

    mysqld_path[in]    location of the mysqld executable

    Returns tuple - (major, minor, release), or None if error
    """
    out = open("version_check", 'w')
    proc = subprocess.Popen("%s --version" % mysqld_path,
                            stdout=out, stderr=out, shell=True)
    proc.wait()
    out.close()
    out = open("version_check", 'r')
    line = None
    for line in out.readlines():
        if "Ver" in line:
            break
    out.close()

    try:
        os.unlink('version_check')
    except:
        pass

    if line is None:
        return None
    version = line.split(' ', 5)[3]
    try:
        maj_ver, min_ver, dev = version.split(".")
        rel = dev.split("-")
        return (maj_ver, min_ver, rel[0])
    except:
        return None

    return None


def show_file_statistics(file_name, wild=False, out_format="GRID"):
    """Show file statistics for file name specified

    file_name[in]    target file name and path
    wild[in]         if True, get file statistics for all files with prefix of
                     file_name. Default is False
    out_format[in]   output format to print file statistics. Default is GRID.
    """

    def _get_file_stats(path, file_name):
        """Return file stats
        """
        stats = os.stat(os.path.join(path, file_name))
        return ((file_name, stats.st_size, time.ctime(stats.st_ctime),
                 time.ctime(stats.st_mtime)))

    columns = ["File", "Size", "Created", "Last Modified"]
    rows = []
    path, filename = os.path.split(file_name)
    if wild:
        for _, _, files in os.walk(path):
            for f in files:
                if f.startswith(filename):
                    rows.append(_get_file_stats(path, f))
    else:
        rows.append(_get_file_stats(path, filename))

    print_list(sys.stdout, out_format, columns, rows)


def remote_copy(filepath, user, host, local_path, verbosity=0):
    """Copy a file from a remote machine to the localhost.

    filepath[in]       The full path and file name of the file on the remote
                       machine
    user[in]           Remote login
    local_path[in]     The path to where the file is to be copie

    Returns bool - True = succes, False = failure or exception
    """

    if os.name == "posix":  # use scp
        run_cmd = "scp %s@%s:%s %s" % (user, host, filepath, local_path)
        if verbosity > 1:
            print("# Command =%s" % run_cmd)
        print("# Copying file from %s:%s to %s:" %
              (host, filepath, local_path))
        proc = subprocess.Popen(run_cmd, shell=True)
        proc.wait()
    else:
        print("Remote copy not supported. Please use UNC paths and omit "
              "the --remote-login option to use a local copy operation.")
    return True

def copy_2_remote(filepath, user, host, remote_path, verbosity=0):
    """Copy a file from local to  a remote machine  .

    filepath[in]       The full path and file name of the file on the locahost
                       machine
    user[in]           Remote login
    local_path[in]     The path to where the file is to be copie

    Returns bool - True = succes, False = failure or exception
    """

    if os.name == "posix":  # use scp
        run_cmd = "scp  %s %s@%s:%s " % (filepath, user, host,  remote_path)
        if verbosity > 1:
            print("# Command =%s" % run_cmd)
        print("# Copying file %s to  %s:%s  " %
              (filepath,host,  remote_path))
        proc = subprocess.Popen(run_cmd, shell=True)
        proc.wait()
    else:
        print("Remote copy not supported. Please use UNC paths and omit "
              "the --remote-login option to use a local copy operation.")
    return True


def check_python_version(min_version=PYTHON_MIN_VERSION,
                         max_version=PYTHON_MAX_VERSION,
                         raise_exception_on_fail=False,
                         name=None, print_on_fail=True,
                         exit_on_fail=True,
                         return_error_msg=False):
    """Check the Python version compatibility.

    By default this method uses constants to define the minimum and maximum
    Python versions required. It's possible to override this by passing new
    values on ``min_version`` and ``max_version`` parameters.
    It will run a ``sys.exit`` or raise a ``UtilError`` if the version of
    Python detected it not compatible.

    min_version[in]               Tuple with the minimum Python version
                                  required (inclusive).
    max_version[in]               Tuple with the maximum Python version
                                  required (exclusive).
    raise_exception_on_fail[in]   Boolean, it will raise a ``UtilError`` if
                                  True and Python detected is not compatible.
    name[in]                      String for a custom name, if not provided
                                  will get the module name from where this
                                  function was called.
    print_on_fail[in]             If True, print error else do not print
                                  error on failure.
    exit_on_fail[in]              If True, issue exit() else do not exit()
                                  on failure.
    return_error_msg[in]          If True, and is not compatible
                                  returns (result, error_msg) tuple.
    """

    # Only use the fields: major, minor and micro
    sys_version = sys.version_info[:3]

    # Test min version compatibility
    is_compat = min_version <= sys_version

    # Test max version compatibility if it's defined
    if is_compat and max_version:
        is_compat = sys_version < max_version

    if not is_compat:
        if not name:
            # Get the utility name by finding the module
            # name from where this function was called
            frm = inspect.stack()[1]
            mod = inspect.getmodule(frm[0])
            mod_name = os.path.splitext(
                os.path.basename(mod.__file__))[0]
            name = '{0} utility'.format(mod_name)

        # Build the error message
        if max_version:
            max_version_error_msg = 'or higher and lower than %s' % \
                '.'.join([str(el) for el in max_version])
        else:
            max_version_error_msg = 'or higher'

        error_msg = (
            'The %(name)s requires Python version %(min_version)s '
            '%(max_version_error_msg)s. The version of Python detected was '
            '%(sys_version)s. You may need to install or redirect the '
            'execution of this utility to an environment that includes a '
            'compatible Python version.'
        ) % {
            'name': name,
            'sys_version': '.'.join([str(el) for el in sys_version]),
            'min_version': '.'.join([str(el) for el in min_version]),
            'max_version_error_msg': max_version_error_msg
        }

        if raise_exception_on_fail:
            raise UtilError(error_msg)

        if print_on_fail:
            print('ERROR: {0}'.format(error_msg))

        if exit_on_fail:
            sys.exit(1)

        if return_error_msg:
            return is_compat, error_msg

    return is_compat


def check_port_in_use(host, port):
    """Check to see if port is in use.

    host[in]            Hostname or IP to check
    port[in]            Port number to check

    Returns bool - True = port is available, False is not available
    """
    try:
        sock = socket.create_connection((host, port))
    except socket.error:
        return True
    sock.close()
    return False


def requires_encoding(orig_str):
    r"""Check to see if a string requires encoding

    This method will check to see if a string requires encoding to be used
    as a MySQL file name (r"[\w$]*").

    orig_str[in]        original string

    Returns bool - True = requires encoding, False = does not require encoding
    """
    ok_chars = re.compile(r"[\w$]*")
    print 'ok_chars : ' , ok_chars
    parts = ok_chars.findall(orig_str)
    return len(parts) > 2 and parts[1].strip() == ''


def encode(orig_str):
    r"""Encode a string containing non-MySQL observed characters

    This method will take a string containing characters other than those
    recognized by MySQL (r"[\w$]*") and covert them to embedded ascii values.
    For example, "this.has.periods" becomes "this@002ehas@00e2periods"

    orig_str[in]        original string

    Returns string - encoded string or original string
    """
    # First, find the parts that match valid characters
    ok_chars = re.compile(r"[\w$]*")
    parts = ok_chars.findall(orig_str)

    # Now find each part that does not match the list of valid characters
    # Save the good parts
    i = 0
    encode_parts = []
    good_parts = []
    for part in parts:
        if not len(part):
            continue
        good_parts.append(part)
        if i == 0:
            i = len(part)
        else:
            j = orig_str[i:].find(part)
            encode_parts.append(orig_str[i:i + j])
            i += len(part) + j

    # Next, convert the non-valid parts to the form @NNNN (hex)
    encoded_parts = []
    for part in encode_parts:
        new_part = "".join(["@%04x" % ord(c) for c in part])
        encoded_parts.append(new_part)

    # Take the good parts and the encoded parts and reform the string
    i = 0
    new_parts = []
    for part in good_parts[:len(good_parts) - 1]:
        new_parts.append(part)
        new_parts.append(encoded_parts[i])
        i += 1
    new_parts.append(good_parts[len(good_parts) - 1])

    # Return the new string
    return "".join(new_parts)


def requires_decoding(orig_str):
    """Check to if a string required decoding

    This method will check to see if a string requires decoding to be used
    as a filename (has @NNNN entries)

    orig_str[in]        original string

    Returns bool - True = requires decoding, False = does not require decoding
    """
    return '@' in orig_str


def decode(orig_str):
    r"""Decode a string containing @NNNN entries

    This method will take a string containing characters other than those
    recognized by MySQL (r"[\w$]*") and covert them to character values.
    For example, "this@002ehas@00e2periods" becomes "this.has.periods".

    orig_str[in]        original string

    Returns string - decoded string or original string
    """
    parts = orig_str.split('@')
    if len(parts) == 1:
        return orig_str
    new_parts = [parts[0]]
    for part in parts[1:]:
        # take first four positions and convert to ascii
        new_parts.append(chr(int(part[0:4], 16)))
        new_parts.append(part[4:])
    return "".join(new_parts)


def check_connector_python(print_error=True):
    """ Check to see if Connector/Python is installed and accessible

    print_error[in]     if True, print the error. Default True

    Prints error and returns False on failure to find connector.
    """
    try:
        import mysql.connector  # pylint: disable=W0612
    except ImportError:
        if print_error:
            print("ERROR: The MySQL Connector/Python module was not found. "
                  "MySQL Utilities requires the connector to be installed. "
                  "Please check your paths or download and install the "
                  "Connector/Python from http://dev.mysql.com.")
        return False
    return True


def print_elapsed_time(start_time):
    """Print the elapsed time to stdout (screen)

    start_time[in]      The starting time of the test
    """
    stop_time = time.time()
    display_time = stop_time - start_time
    print("Time: {0:.2f} sec\n".format(display_time))
