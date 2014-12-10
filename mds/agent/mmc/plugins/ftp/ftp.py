from tempfile import mkstemp
from shutil import move
from os import remove, close, path, mkdir, chown, chmod
from mmc.support.mmctools import shLaunch
import re
import grp
import pwd
import shutil

class Ftp(object):
	#set global FTP configurations if the parameter do not exists on file, append it
	def setConf(self, param, key):
		#php can pass or not some key values, if not do nothing
		if key:
			if(param.startswith("#")):#to enable/disable this kind of parameter has to uncomment or comment then do this
				param = param[1:] #remove flag '#'
				rt1 = shLaunch("grep '^#"+ param +"' /etc/proftpd.conf")
				rt2 = shLaunch("grep '^"+ param +"' /etc/proftpd.conf")
				if(rt1.exitCode == 0):
					shLaunch("sed -i 's,^#" + param +".*,"+ param +" "+ key +",g' /etc/proftpd.conf")
				elif(rt2.exitCode == 0):
					shLaunch("sed -i 's,^" + param +".*,#"+ param +" "+ key +",g' /etc/proftpd.conf")
				else: #do not exists, create it
					self.insertConf("/etc/proftpd.conf",'^' + param, ' ' + key + '\n')
				shLaunch("service proftpd restart")
				return 0

			rt = shLaunch("cat /etc/proftpd.conf | grep '" + param + "' ")
			if(rt.exitCode != 0):
				self.insertConf("/etc/proftpd.conf", '^' + param, '\t\t\t' + key + '\n')
			else:
				self.replaceConf("/etc/proftpd.conf", '^' + param, '\t\t\t' + key + '\n')
			shLaunch("service proftpd restart")
			return 0

	#return 0 = ok, return 1 if the dir do not exists in the path variable
	def setAnonPath(self,pth,maxuser):
		if(pth != 'remove'):
			rt = shLaunch('[ -d '+ pth + ' ]')
			if rt.exitCode != 0:
				return 1
			rt = shLaunch("cat /etc/proftpd.conf | grep -E '^<Anonymous '")
			if(rt.exitCode != 0): #if <Anonymous conf do not exists in file create it
				fh = open('/etc/proftpd.conf','a')
				fh.write('<Anonymous ' + pth +' >\n')
				fh.write('\t# Allow logins if they are disabled above.\n')
				fh.write('\t<Limit LOGIN>\n')
				fh.write('\t\tAllowAll\n')
				fh.write('\t</Limit>\n')
				fh.write('\n')
				fh.write('\t# Maximum clients with message\n')
				fh.write('\tMaxClients\t\t\t'+ maxuser +' "Sorry, max %m users -- try again later"\n')
				fh.write('\n')
				fh.write('\tUser\t\t\tftp\n')
				fh.write('\tGroup\t\t\tftp\n')
				fh.write('\t# We want clients to be able to login with "anonymous" as well as "ftp"\n')
				fh.write('\tUserAlias\t\t\tanonymous\tftp\n')
				fh.write('\tRequireValidShell\t\t\toff\n')
				fh.write('\n')
				fh.write('\t# Limit WRITE everywhere in the anonymous chroot\n')
				fh.write('\t<Limit WRITE>\n')
				fh.write('\t\tDenyAll\n')
				fh.write('\t</Limit>\n')
				fh.write('</Anonymous>\n')
				fh.close()
			else: #if exists just change the path
				self.replaceConf('/etc/proftpd.conf','^<Anonymous',' ' + pth +' >\n')
				self.replaceConf('/etc/proftpd.conf','\tMaxClients', ' ' + maxuser + ' "Sorry, max %m users -- try again later"\n')
		# remove anonymous lines bellow <Anonymous.. until </Anonymous>
		else:
			aux = 0 #control variable to write or not in file
			r = open("/etc/proftpd.conf")
			lines = r.readlines()
			r.close()
			w = open("/etc/proftpd.conf",'w')
			w.writelines(''); #clean up .conf file before write
			for word in lines:
				if(re.match('^\<Anonymous*', word) is not None):#if true do not write
					aux=1
				if(aux == 0):
					w.write(word)
				if(re.match('^\</Anonymous*', word) is not None): # if true write to file
					aux=0
			w.close()
		shLaunch('service proftpd restart')
		return 0

	#test if public share is enabled
	def isEnabled(self,pattern):
		ret = shLaunch("grep -E '"+ pattern +"' /etc/proftpd.conf")
		if(ret.exitCode == 0): #its enabled
			return 1
		else:# its not
			return 0


	#replace some configuration making temp file and replacing what you want to temp file
	def replaceConf(self, file_path, pattern, key):
		fh, abs_path = mkstemp()
		new_file = open(abs_path,'w')
		old_file = open(file_path)
		for line in old_file:
			if(re.match(pattern, line) is not None):
				new_file.write(pattern.translate(None,'^&$?*') + key) #remove the special symbols for regex pattern
			else:
				new_file.write(line)
		new_file.close()
		close(fh)
		old_file.close()
		remove(file_path)
		move(abs_path, file_path)
	#or just append the new configuration to the end of the file
	def insertConf(self, file_path, pattern, key):
		fh = open(file_path,'a')
		fh.write(pattern.translate(None, '^&$?*') + key) #remove the special symbols for regex pattern
		fh.close()
	#input regex to find in file, return value of the param in the config file
	def getConf(self, param):
		param = param.translate(None, '^$?*')
		ret = shLaunch("grep '" + param + "' /etc/proftpd.conf | sed 's/"+ param +"[\\t| |\\n]*//g'")
		ret.out = ret.out.replace('\n', '')
		ret.out = ret.out.replace('"', '')
		return ret.out
	#enable ftp share for each user, return 2 = user do not exists, 1 = file exists, 0 = everything ok
	def ftpEnableUser(self, name):
		ret=path.isdir('/home/' + name)
		if not ret:
			return 2
		ret=path.isdir("/home/" + name + "/share_ftp")
		if not ret:
			try:
				pwd.getpwnam(name)
			except KeyError:
				return 2
			mkdir('/home/' + name + '/share_ftp')
			uid = pwd.getpwnam(name).pw_uid
			gid = grp.getgrnam("ftp").gr_gid
			chown("/home/" + name + "/share_ftp", uid, gid)
			chmod("/home/" + name + "/share_ftp", 0755)
			return 0
		else:
			return 1
	def ftpDisableUser(self, name):
		ret=path.isdir('/home/' + name)
		if not ret:
			return 2
		ret=path.isdir("/home/" + name + "/share_ftp")
		if ret:
			shutil.rmtree('/home/' + name + '/share_ftp')
			return 0
		else:
			return 1
	#get all users with ftp share anabled
	def ftpGetUsers(self):
		ret = shLaunch("find /home -maxdepth 2 -name 'share_ftp' -type d | cut -d / -f 3")
		users = ret.out
		users = users.split('\n')
		users = [x for x in users if x]
		if len(users) == 0:
			return 0
		else:
			return users
