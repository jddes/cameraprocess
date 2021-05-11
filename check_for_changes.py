import os
import time

import win32file
import win32con


ACTIONS = {
    1 : "Created",
    2 : "Deleted",
    3 : "Updated",
    4 : "Renamed to something",
    5 : "Renamed from something"
}
# Thanks to Claudio Grondi for the correct set of numbers
FILE_LIST_DIRECTORY = 0x0001

path_to_watch = "d:\\repo\\CameraProcess\\images"
files_to_watch = {}
target_size = 2998

hDir = win32file.CreateFile (
    path_to_watch,
    FILE_LIST_DIRECTORY,
    win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
    None,
    win32con.OPEN_EXISTING,
    win32con.FILE_FLAG_BACKUP_SEMANTICS,
    None
)
queue.Queue(maxsize=1000)

while 1:
    #
    # ReadDirectoryChangesW takes a previously-created
    # handle to a directory, a buffer size for results,
    # a flag to indicate whether to watch subtrees and
    # a filter of what changes to notify.
    #
    # NB Tim Juchcinski reports that he needed to up
    # the buffer size to be sure of picking up all
    # events when a large number of files were
    # deleted at once.
    #
    results = win32file.ReadDirectoryChangesW (
        hDir,
        int(1e6),
        True,
        win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
        # win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
        # win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
        win32con.FILE_NOTIFY_CHANGE_SIZE,
        # win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
        # win32con.FILE_NOTIFY_CHANGE_SECURITY,
        None,
        None
    )


    bRunZip = False
    for action, file in results:
        full_filename = os.path.join (path_to_watch, file)
        files_to_watch[full_filename] = 1

    for file in files_to_watch:
        try:
            size = os.path.getsize(file)
            if size == target_size:
                print("%s: %d" % (file, size))
                
                q.put(file)
        except OSError as e:
            print("%s: OSError: %s" % (file, e.strerror))

