#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Related RFCs: 2047, 2044, 1522

# GREETZ: PABLO CASTELLANO, original author of most of the code



import mailbox
import base64
import os
import sys
import email
import magic
import requests

REST_URL = "http://192.168.0.106:8090/tasks/create/file"

BLACKLIST = ('signature.asc', 'message-footer.txt', 'smime.p7s')
VERBOSE = 1

attachments = 0 #Count extracted attachment
skipped = 0


def check_executable(fil):
	form = magic.from_file(fil)
	if "executable" in form:
		return True
	else:
		return False

def cuckoo_submit(fil):
	with open(fil, "rb") as sample:
		files = {"file": ("temp_file_name", sample)}
		r = requests.post(REST_URL, files=files)
		task_id = r.json()["task_id"]
		return task_id
	
# Search for filename or find recursively if it's multipart
def extract_attachment(payload):
	global attachments, skipped
	filename = payload.get_filename()

	if filename is not None:
		print "\nAttachment found!"
		if filename.find('=?') != -1:
			ll = email.header.decode_header(filename)
			filename = ""
			for l in ll:
				filename = filename + l[0]
			
		if filename in BLACKLIST:
			skipped = skipped + 1
			if (VERBOSE >= 1):
				print "Skipping %s (blacklist)\n" %filename
			return


		content = payload.as_string()
		# Skip headers, go to the content
		fh = content.find('\n\n')
		content = content[fh:]

		# if it's base64....
		if payload.get('Content-Transfer-Encoding') == 'base64':
			content = base64.decodestring(content)
		# quoted-printable
		# what else? ...

		print "Extracting %s (%d bytes)\n" %(filename, len(content))

		n = 1
		orig_filename = filename
		while os.path.exists(filename):
			filename = orig_filename + "." + str(n)
			n = n+1

		try:
			fp = open(filename, "w")
#			fp = open(str(i) + "_" + filename, "w")
			fp.write(content)
		except IOError:
			print "Aborted, IOError!!!"
			sys.exit(2)
		finally:
			fp.close()
			if (check_executable(filename)):
				print "it is executable, submitting"
				cuckoo_submit(filename)
			else:
				print "it is not executable"

		attachments = attachments + 1
	else:
		if payload.is_multipart():
			for payl in payload.get_payload():
				extract_attachment(payl)


###
print "Submit executable attachments  from postfix mailboxes to cuckoo sandbox via it's API"
print "Greetz Pablo Castellano for most of the code and Pau Munoz for some fixes and cuckoo interface"
print "This program comes with ABSOLUTELY NO WARRANTY."
print "This is free software, and you are welcome to redistribute it under certain conditions."
print

if len(sys.argv) < 2 or len(sys.argv) > 3:
	print "Usage: %s <mbox_file> [directory]" %sys.argv[0]
	sys.exit(0)

filename = sys.argv[1]
directory = os.path.curdir

if not os.path.exists(filename):
	print "File doesn't exist:", filename
	sys.exit(1)

if len(sys.argv) == 3:
	directory = sys.argv[2]
	if not os.path.exists(directory) or not os.path.isdir(directory):
		print "Directory doesn't exist:", directory
		sys.exit(1)

mb = mailbox.mbox(filename)
nmes = len(mb)

os.chdir(directory)

for i in range(len(mb)):
	if (VERBOSE >= 2):
		print "Analyzing message number", i

	mes = mb.get_message(i)
	em = email.message_from_string(mes.as_string())

	subject = em.get('Subject')
	if subject.find('=?') != -1:
		ll = email.header.decode_header(subject)
		subject = ""
		for l in ll:
			subject = subject + l[0]

	em_from = em.get('From')
	if em_from.find('=?') != -1:
		ll = email.header.decode_header(em_from)
		em_from = ""
		for l in ll:
			em_from = em_from + l[0]

	if (VERBOSE >= 2):
		print "%s - From: %s" %(subject, em_from)

	filename = mes.get_filename()
	
	if em.is_multipart():
		for payl in em.get_payload():
			extract_attachment(payl)
	else:
		extract_attachment(em)

print "\n--------------"
print "Total attachments extracted:", attachments
print "Total attachments skipped:", skipped
