# -*- coding: utf-8 -*-
"""

Google File Duplicate Toolkit

by Casten Riepling

This includes a few utlities to aid in the removal of duplicate folders from Google drive.

"""

from __future__ import print_function
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import pprint
import json
import time
from datetime import timedelta


######################################################################################################
# Examples - These use the top flows to show interesting data


# step_one_Query_Google_and_save - Get the data from Google, save to a local file and print out a small summary
def step_one_query_google_and_save():
    all_files = read_write_all_files()
    print_type_breakdown(all_files)


# step_two_Read_and_Print_dupe_top_folder_info - Load the master file list from disk and print the
def step_two_read_and_print_dupe_folder_info():

    # Get the info from disk
    all_files = read_all_files_from_disk()

    # Get a simplified representation
    all_files_simplified = simplify_items(all_files)

    add_children_info(all_files_simplified)
    swizzle_parent_info(all_files_simplified)
    suspicious_folders = get_suspicious_folder_info(all_files_simplified)

    suspicious_folders.sort(key=lambda r: r[0], reverse=True)

    print('Top Folders: ', end='')
    for i in range(0, 5):
        pprint.pprint(suspicious_folders[i], depth=3)

    return suspicious_folders


def get_sizes_for_files(files):
    # Get the info from disk
    all_files = read_all_files_from_disk()

    # Get a simplified representation
    all_files_simplified = simplify_items(all_files)

    add_children_info(all_files_simplified)
    swizzle_parent_info(all_files_simplified)
    suspicious_folders = get_suspicious_folder_info(all_files_simplified)

    suspicious_folders.sort(key=lambda r: r[0], reverse=True)
    for fileId in files:
        file_item = all_files_simplified[fileId]
        info = get_folder_info(file_item)
        print(fileId+' size: '+str(info[0])+' count: '+str(info[1]))


######################################################################################################
# Helper functions

# get_all_files - Gets all the non-trashed files
def get_all_files(service):
    page_token = None
    param = {'pageSize': 1000, 'fields': "nextPageToken, files", 'q': "trashed = false"}
    allItems = {}
    while True:
        if page_token:
            param['pageToken'] = page_token
            print('Next page: ' + page_token)
        some_files = service.files().list(**param).execute()
        items = some_files.get('files')
        for item in items:
            if 'id' not in item:
                raise Exception('no id in item' + str(item))
            allItems[item['id']] = item

        page_token = some_files.get('nextPageToken')
        if not page_token:
            break
    return allItems


# write_tree - Writes an object (normally a dictionary) to disk
def write_tree(tree, filename):
    s = json.dumps(tree)
    f1 = open(filename, 'w')
    f1.write(s)
    f1.close()


# read_all_files_from_disk - Reads "all_files.json" from disk, returns the dictionary
def read_all_files_from_disk():
    f1 = open('all_files.json', 'r')
    s = f1.read()
    f1.close()
    return json.loads(s)


# collect_dupes - Given two lists of lists, select lists that have more than one item.
#               This will be the two lists with potential duplicate items.
def collect_dupes(all_names, all_md5s):
    dupe_names = {}
    for key, items in all_names.items():
        if len(items) > 1:
            dupe_names[key] = items
    dupe_md5s = {}
    for key, items in all_md5s.items():
        if len(items) > 1:
            dupe_md5s[key] = items
    return dupe_names, dupe_md5s


# get_dupes - Given all files, return two lists of potential duplicates (dupe names, dupe md5)
def get_dupes(all_files):
    all_names, all_md5s = bin_all(all_files)
    return collect_dupes(all_names, all_md5s)


def get_name(item):
    return item['name']


def list_names(folder):
    return list(map(get_name, folder))


def print_list(the_list, desc):
    print(desc + pprint.pformat(list_names(the_list), indent=10))


# given a list of potential duplicate items, calculate the potential redundant files
def calculate_redundancy(dupes):
    total = 0
    for key in dupes:
        item = dupes[key]
        for i in range(1, len(item)):
            total += int(item[i]['size'])
    return total


# trim_tree - Create a new tree with only the bare necessary information
def simplify_items(items):
    new_tree = {}
    for key in items:
        curr_item = items[key]
        new_item = {}
        if 'name' in curr_item:
            new_item['name'] = curr_item['name']
        if 'md5Checksum' in curr_item:
            new_item['md5Checksum'] = curr_item['md5Checksum']
        if 'size' in curr_item:
            new_item['size'] = curr_item['size']
        if 'id' in curr_item:
            new_item['id'] = curr_item['id']
        if 'parents' in curr_item:
            new_item['parents'] = curr_item['parents']
        if 'children' in curr_item:
            new_item['children'] = curr_item['children']
        else:
            new_item['children'] = []
        new_tree[key] = new_item
    return new_tree


# get_dupe_folders - return just the folders that have dupe entries
def get_dupe_folders(flat):
    dupe_folders = {}
    for key in flat:
        curr_item = flat[key]
        if len(curr_item) > 1:
            dupe_folders[key] = curr_item
    return dupe_folders


# get_folder_info - given a folder item, return the total contained (size, file count).  This includes child folders.
def get_folder_info(folder_item):
    total_size = 0
    total_files = 0
    if 'children' not in folder_item:
        return 0,0
    for child in folder_item['children']:
        if 'md5Checksum' not in child:
            # This is a folder, so recurse down
            size, count = get_folder_info(child)
            total_size += size
            total_files += count + 1 # add one extra to count this folder
        else:
            total_files += 1
            total_size += int(child['size'])
    return total_size, total_files


# get_suspicious_folder_info - return a list of items where:
#                                   the total size of children files are the same
#                                   the total number of files are the same
#                                   the number of folders that share these properties is > 1
def get_suspicious_folder_info(all_files):
    suspicious_folders = {}
    # Go through all items and determine the total file count and size, recursing as necessary.
    # We'll make a master dictionary of all sizes and folder counts for each size.
    # The reasoning being, if sizes and folders match, we've got a possible dupe.

    # The structure looks like
    # {
    #   '100': {
    #               '4': [item1]
    #           },
    #   '56': {
    #               '3': [item2],
    #               '4': [item3, item4]
    #           }
    # }
    for id in all_files:
        item = all_files[id]
        # Skip over files
        if 'md5Checksum' in item:
            continue
        if 'mimeType' in item and item['mimeType'] != 'application/vnd.google-apps.folder' :
            continue
        folder_size, folder_children = get_folder_info(item)

        # If either sizes are 0, skip this folder
        if folder_size == 0 or folder_children == 0:
            continue

        if folder_size not in suspicious_folders:
            # New size
            suspicious_folders[folder_size] = {folder_children: [item]}
        else:
            # We've seen this size before
            folders_this_size = suspicious_folders[folder_size]
            if folder_children not in folders_this_size:
                # New child count for this size
                folders_this_size[folder_children] = [item]
            else:
                # Duplicate child count
                # But first, be sure there is no common parent
                same_size_same_children = folders_this_size[folder_children]
                for item2 in same_size_same_children:
                    if 'parent' not in item or 'parent' not in item2:
                        continue
                    if item['parent'] == item2['parent']:
                        continue
                # Ok, not a child of existing, so add
                folders_this_size[folder_children].append(item)

    dupes = []
    # Go through all the folder looking for dupe files
    for folder_size in suspicious_folders:
        suspicious_folder = suspicious_folders[folder_size]
        for child_counts in suspicious_folder:
            curr_counts = suspicious_folder[child_counts]
            # If less than 2, it's not a dupe, so add to removal queue
            if len(curr_counts) > 1:
                dupes.append((folder_size, curr_counts))

    return dupes


# separate_file_types - Walks through all files, separates into categories of:
#    external_files, external_folders, drive_root_files, drive_root_folders
#    Also parents children to parents in the dictionary.
def separate_file_types(all_files):
    external_files = []
    external_folders = []
    drive_root_files = []
    drive_root_folders = []
    for key in all_files:
        curr_file = all_files[key]
        if 'parents' in curr_file:
            parent_id = curr_file['parents'][0]
            if parent_id in all_files:
                parent = all_files[parent_id]
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(curr_file['id'])
            else:
                if curr_file['mimeType'] == 'application/vnd.google-apps.folder':
                    drive_root_folders.append(curr_file)
                else:
                    drive_root_files.append(curr_file)

        else:
            if curr_file['mimeType'] == 'application/vnd.google-apps.folder':
                external_folders.append(curr_file)
            else:
                external_files.append(curr_file)
    return external_folders, external_files, drive_root_folders, drive_root_files


# bin_all -Makes two bins, one with all names, another with md5s.
#       Each bin is a list of items for those identifiers, name or md5.
#       For items in the name bin, these _may_ indicate duplicates.  This may include
#       both files and folders.
#       For items in the md5 bin, these are very likely duplicates.  These will always
#       be files since only a file can have an md5 checksum.
def bin_all(all_files):
    all_md5s = {}
    all_names = {}
    for id in all_files:
        item = all_files[id]
        if 'md5Checksum' in item:
            currMd5 = item['md5Checksum']
            if currMd5 not in all_md5s:
                all_md5s[currMd5] = []
            all_md5s[currMd5].append(item)
        if 'name' in item:
            name = item['name']
            if name not in all_names:
                all_names[name] = []
            all_names[name].append(item)
    return all_names, all_md5s


######################################################################################################
#   Top Level Flows
#
#  These are high level calls to get and process file info.


# read_write_all_files -    Gets all the files in te root Google Drive, writes them to a local json file,
#                           and returns the result.
#                           Depending on the number of files in the Google Drive, this may take a while to complete.
#                           200GB with a 150Mb/s connection takes about 9 minutes
#                           Subsequent retrievals can be performed using the file data (defaults to "all_files.json")
def read_write_all_files(filename='all_files.json'):
    """Shows basic usage of the Drive v3 API.
    Prints the names and ids of the first 10 files the user has access to.
    """
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    store = file.Storage('token.json')
    creds = store.get()

    # If modifying these scopes, delete the file token.json.
    SCOPES = 'https://www.googleapis.com/auth/drive.metadata.readonly'

    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('drive', 'v3', http=creds.authorize(Http()))

    print('Querying Google via Drive API v3.  This may take a while...')
    start = time.time()
    all_files = get_all_files(service)
    stop = time.time()

    elapsed = timedelta(seconds=(stop - start))

    print('Elapsed time to retrieve data from Google: ' + str(elapsed))

    s = json.dumps(all_files)
    f1 = open(filename, 'w')
    f1.write(s)
    f1.close()

    return all_files


# print_type_breakdown - Prints root level files and folders of different types
# External folders are things like:
#   * Folders shared from other users
#   * Backed Up Computers from Google Backup And Sync
# External Files are things like:
#   * Files shared with you by other users
# Drive Root Folders are things like:
#   * Top level Drive folders
#   * Google Photos
# Drive root files are things like:
#   * Uploaded files at the drive root
#   * Google Docs, Sheets, etc.
def print_type_breakdown(files):
    external_folders, external_files, drive_root_folders, drive_root_files = separate_file_types(files)
    print_list(external_folders, 'External folders: ')
    print_list(external_files, 'External files: ')
    print_list(drive_root_folders, 'Drive root folders: ')
    print_list(drive_root_files, 'Drive root files: ')


# add_children_info - Given a list of item ids, find the parents and add a reference to this item in a
#                       'children' list element
def add_children_info(items):
    for item_id in items:
        item = items[item_id]
        if 'parents' in item and len(item['parents']) > 0:
            parent_id = item['parents'][0]
            if parent_id in items:
                parent = items[parent_id]
                if 'children' not in parent:
                    parent['children'] = []
                parent['children'].append(items[item_id])


# swizzle_parent_info - add an object reference for parents rather than just an id
def swizzle_parent_info(items):
    for item_id in items:
        item = items[item_id]
        if 'parents' in item and len(item['parents']) > 0:
            parent_id = item['parents'][0]
            if parent_id in items:
                parent = items[parent_id]
                item['parent'] = parent


######################################################################################################
# Main

if __name__ == '__main__':
    # step_one_query_google_and_save()
    step_two_read_and_print_dupe_folder_info()
    # get_sizes_for_files(['1gOxRqXl69IRmg48_p47qO2uwyA0kTuL8', '1eCEeykgyQfmJhkJZDO7Do9XzZnU9TBPP', '1nG7mNGfJ9HerJLhuiCHFGxbAL9DqGUdK', '1v51PnZ_yt44AZ3G9C4unI7p9aftVQykh'])
