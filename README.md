# GoogleDriveDupeToolkit
A set of tools useful for identifying and locating duplicates in your Google Drive.  Written in Python3.

# Audience
Being a toolkit, the intended audience for this is developers.  There is no UI and examples are very limited.  That being said, they were useful to me.

## Warning
These tools are experimental and for research only.  While they do not attempt to modify any of the remote files, I can't be held responsible for any damage that may occur.  Read the code, there is not much.  Use at your own risk!

## Dependencies
You'll need to install and configure if necessary the following python libraries - googleapiclient, oauth2client, httplib2

## Notes
This toolkit includes a few high level functions for checking for duplicate folders throughout your Google Drive.  It will work across normal Drive locations as well as Computer Backups.  It does not look in the trash folder.

These utilities are not optimized.  Most work is processed using the Google Drive API's and in memory.  You have the option to save information to disk to speed up subequent queries.  Observed performance for initial retrieval of file metadata is on the order of 8 minutes to pull down metadata for 200GB of what I'd consider typical and smallish files.  The local cached metadata for 200GB of files is about 200MB.  YMMV.

The goal of the toolkit is to provide some primitives and some examples for accessin and processing Google Drive APIs.

## Use
Typical usage might be something like:

1.  Run step_one_query_google_and_save()   (About 8 minutes for 200 GB)
2.  Run step_two_read_and_print_dupe_folder_info() to find the largest offenders
3.  Look up offenders by name or by id.  Google drive URLs in a browser typically look something like:
          https://driveURL/blah/blah$fileID
        e.g.:
          https://drive.google.com/drive/u/0/folders/2n5GeYJOD10jiEdAIVO8qpWG5gEZFsA2Z
    When you find an interesting file id, you can plug it into the browser to check things out.
    You can also query by folder name to see if there are other related dupes that may have partials.

4.  Note the ids and/or names of all potential matches and feed into get_sizes_for_files() to verify file sizes and count.
5.  Finally, manually remove all duplicate data through Google Drive UI.

## Origin Story

I had multiple machines and used various backup solutions and software over the years.  I migrated everything to Google Drive once the prices lowered to competetive levels.  On various machines and NAS there existed duplicate, often several, copies of the same data.  Additionally, during the process of consolidating data and transferrin to Google Drive, where I wanted to merge folders, often they were simply duplicated.

