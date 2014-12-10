import re
import logging
from os.path import exists
from os import mkdir
from mmc.core.version import scmRevision
from mmc.support.mmctools import shLaunch
from mmc.support.config import PluginConfig, ConfigException
from ConfigParser import NoSectionError, NoOptionError
from mmc.plugins.ftp.ftp import Ftp

VERSION="1.0.0"
APIVERSION="1:0:0"
REVISION = scmRevision("$Rev$")

def getVersion(): return VERSION
def getApiVersion(): return APIVERSION
def getRevision(): return REVISION

def activate():
	config = FtpConfig("ftp")
	ldapconf = LdapConfig("base")
	logger = logging.getLogger()

	if config.disabled:
		ret = shLaunch("service proftpd status")
		if ret.exitCode == 0:
			shLaunch("service proftpd stop")
		logger.warning("Plugin ftp: disabled by configuration.")
		return False
	ret = shLaunch("rpm -qa | grep -E '^proftpd-([0-9]\.)+.*'")
	if ret.exitCode != 0:
		logger.warning("Plugin ftp: proftpd package not installed, trying to install now...")
		ret = shLaunch("urpmi proftp --auto --force")
		if ret.exitCode != 0:
			logger.error("Plugin ftp: could not install proftp package as requirement for this module")
			return False
	ret = shLaunch("rpm -qa | grep '^proftpd-mod_ldap'")
	if ret.exitCode != 0:
		logger.warning("Plugin ftp: proftpd-mod_ldap package not installed, trying to install now...")
		ret = shLaunch("urpmi proftpd-mod_ldap --auto --force")
		if ret.exitCode != 0:
			logger.error("Plugin ftp: could not install proftpd-mod_ldap package as requirement for this module")
			return False
	#open port for FTP in shorewall plugin
	ret = shLaunch("service shorewall status")
	if ret.exitCode != 1:#shorewall service exists then...
		ret = shLaunch("cat /etc/shorewall/rules | grep -P 'FTP/ACCEPT\tlan[0-9]+\tfw'")
		if ret.exitCode != 0:#add rule for all vlans and lans if it not exists already
			logger.warning("Plugin ftp: Unblocking port 21 in shorewall rules...")
			shLaunch("mss-add-shorewall-rule -a FTP/ACCEPT -t lan")
			shLaunch("service shorewall restart")
	#test if ldap module config exists, if not create one
	if (not exists("/etc/proftpd.d")):
			mkdir("/etc/proftpd.d")
	ret = shLaunch("ls /etc/proftpd.d/*ldap*")
	if (ret.exitCode != 0):
		fh = open("/etc/proftpd.d/13_mod_ldap.conf", "w")
		fh.write("LoadModule mod_ldap.c\n")
		fh.close()
	#test if config file exists, if not create a default one
	if (not exists("/etc/proftpd.conf")):
		logger.warning("Plugin ftp: could not find configuration file to ftp in /etc/proftpd.conf, creating it..")
		fh = open("/etc/proftpd.conf", "w")
		fh.write('#\n')
		fh.write('# /etc/proftpd/proftpd.conf -- This is a basic ProFTPD configuration file.\n')
		fh.write('# To really apply changes reload proftpd after modifications.\n')
		fh.write('# \n')
		fh.write('\n')
		fh.write('# Includes DSO modules\n')
		fh.write('Include /etc/proftpd.d/*.conf\n')
		fh.write('\n')
		fh.write('# This is the directory where DSO modules resides\n')
		fh.write('\n')
		fh.write('ModulePath /usr/lib64/proftpd\n')
		fh.write('\n')
		fh.write('# Allow only user root to load and unload modules, but allow everyone\n')
		fh.write('# to see which modules have been loaded\n')
		fh.write('\n')
		fh.write('ModuleControlsACLs insmod,rmmod allow user root\n')
		fh.write('ModuleControlsACLs lsmod allow user *\n')
		fh.write('\n')
		fh.write('ServerName			"Default MBS-FTP Installation"\n')
		fh.write('ServerType			standalone\n')
		fh.write('DeferWelcome			off\n')
		fh.write('\n')
		fh.write('MultilineRFC2228		on\n')
		fh.write('DefaultServer			on\n')
		fh.write('ShowSymlinks			on\n')
		fh.write('\n')
		fh.write('TimeoutNoTransfer		600\n')
		fh.write('TimeoutStalled			600\n')
		fh.write('TimeoutIdle			1200\n')
		fh.write('\n')
		fh.write('DisplayLogin                    welcome.msg\n')
		fh.write('DisplayChdir                    .message\n')
		fh.write('ListOptions                	"-l"\n')
		fh.write('DenyFilter			\*.*/\n')
		fh.write('UseIPv6                         Off\n')
		fh.write('\n')
		fh.write('# Allow FTP resuming.\n')
		fh.write('# Remember to set to off if you have an incoming ftp for upload.\n')
		fh.write('AllowStoreRestart		on\n')
		fh.write('\n')
		fh.write('# Port 21 is the standard FTP port.\n')
		fh.write('Port				21\n')
		fh.write('\n')
		fh.write('# In some cases you have to specify passive ports range to by-pass\n')
		fh.write('# firewall limitations. Ephemeral ports can be used for that, but\n')
		fh.write('# feel free to use a more narrow range.\n')
		fh.write('#PassivePorts                    49152 65534\n')
		fh.write('\n')
		fh.write('# To prevent DoS attacks, set the maximum number of child processes\n')
		fh.write('# to 30.  If you need to allow more than 30 concurrent connections\n')
		fh.write('# at once, simply increase this value.  Note that this ONLY works\n')
		fh.write('# in standalone mode, in inetd mode you should use an inetd server\n')
		fh.write('# that allows you to limit maximum number of processes per service\n')
		fh.write('# (such as xinetd)\n')
		fh.write('MaxInstances			30\n')
		fh.write('\n')
		fh.write('# Set the user and group under which the server will run.\n')
		fh.write('User				nobody\n')
		fh.write('Group				nogroup\n')
		fh.write('\n')
		fh.write('# Umask 022 is a good standard umask to prevent new files and dirs\n')
		fh.write('# (second parm) from being group and world writable.\n')
		fh.write('Umask				022  022\n')
		fh.write('\n')
		fh.write('# To cause every FTP user to be "jailed" (chrooted) into their home\n')
		fh.write('# directory, uncomment this line.\n')
		fh.write('DefaultRoot ~/share_ftp/\n')
		fh.write('\n')
		fh.write('# Normally, we want files to be overwriteable.\n')
		fh.write('AllowOverwrite			on\n')
		fh.write('\n')
		fh.write('# Uncomment this if you are using NIS or LDAP to retrieve passwords:\n')
		fh.write('PersistentPasswd		off\n')
		fh.write('\n')
		fh.write('# Be warned: use of this directive impacts CPU average load!\n')
		fh.write('#\n')
		fh.write('# Uncomment this if you like to see progress and transfer rate with ftpwho\n')
		fh.write('# in downloads. That is not needed for uploads rates.\n')
		fh.write('#UseSendFile			off\n')
		fh.write('\n')
		fh.write('TransferLog /var/log/proftpd/proftpd.log\n')
		fh.write('SystemLog   /var/log/proftpd/proftpd.log\n')
		fh.write('\n')
		fh.write('<IfModule mod_tls.c>\n')
		fh.write('    TLSEngine off\n')
		fh.write('</IfModule>\n')
		fh.write('\n')
		fh.write('<IfModule mod_quota.c>\n')
		fh.write('    QuotaEngine on\n')
		fh.write('</IfModule>\n')
		fh.write('\n')
		fh.write('<IfModule mod_ratio.c>\n')
		fh.write('    Ratios on\n')
		fh.write('</IfModule>\n')
		fh.write('\n')
		fh.write('# Delay engine reduces impact of the so-called Timing Attack described in\n')
		fh.write('# http://security.lss.hr/index.php?page=details&ID=LSS-2004-10-02\n')
		fh.write('# It is on by default. \n')
		fh.write('<IfModule mod_delay.c>\n')
		fh.write('    DelayEngine on\n')
		fh.write('</IfModule>\n')
		fh.write('\n')
		fh.write('<IfModule mod_ctrls.c>\n')
		fh.write('    ControlsEngine        on\n')
		fh.write('    ControlsMaxClients    2\n')
		fh.write('    ControlsLog           /var/log/proftpd/controls.log\n')
		fh.write('    ControlsInterval      5\n')
		fh.write('    ControlsSocket        /var/run/proftpd/proftpd.sock\n')
		fh.write('</IfModule>\n')
		fh.write('\n')
		fh.write('<IfModule mod_ctrls_admin.c>\n')
		fh.write('    AdminControlsEngine on\n')
		fh.write('</IfModule>\n')
		fh.write('\n')
		fh.write('# Bar use of SITE CHMOD by default\n')
		fh.write('<Limit SITE_CHMOD>\n')
		fh.write('    DenyAll\n')
		fh.write('</Limit>\n')
		fh.write('\n')
		fh.close()
		
	#jail all users to their home as default
	ret = shLaunch("grep '^#DefaultRoot.*' /etc/proftpd.conf")
	if ret.exitCode == 0:
		Ftp().setConf('#DefaultRoot','~/share_ftp/')
	else:
		ret = shLaunch("grep '^DefaultRoot.*' /etc/proftpd.conf") 
		if ret.exitCode != 0:
			Ftp().setConf('#DefaultRoot','~/share_ftp/')
		else:# check if the paramters is ~/share_ftp and not ~
			ret = shLaunch("grep '~/share_ftp/' /etc/proftpd.conf")
			if ret.exitCode != 0:
				Ftp().setConf('DefaultRoot','~/share_ftp/')

	#set-up ldap authentication for user in FTP
	ret = shLaunch("grep '^<IfModule mod_ldap.c>' /etc/proftpd.conf")
	if(ret.exitCode != 0):
		fh = open("/etc/proftpd.conf", "a")
		fh.write("<IfModule mod_ldap.c>\n")
		fh.write("\tLDAPServer ldap://"+ ldapconf.host +"/??sub\n")
		fh.write('\tLDAPDNInfo "'+ ldapconf.root +'" "' + ldapconf.passw +'"\n')
		fh.write('\tLDAPDoAuth on "' + ldapconf.userdn +'" (&(uid=%v)(objectclass=posixAccount))\n')
		fh.write('\tLDAPDoUIDLookups on "' + ldapconf.userdn +'"\n')
		fh.write('\tLDAPDoGIDLookups on "'+ ldapconf.groupdn +'"\n')
		fh.write("</IfModule>\n")
		fh.close()
	ret = shLaunch("service proftpd restart")
	return True

# XML-RPC declarations

def setConf(param, key):
	Ftp().setConf(param, key)
def setAnonPath(path,maxuser):
	return Ftp().setAnonPath(path,maxuser)
def isFtpConfEnabled(pattern):
	return Ftp().isEnabled(pattern)
def getFtpConf(param):
	return Ftp().getConf(param)
def ftpGetUsers():
	return Ftp().ftpGetUsers()
def ftpDisableUser(user):
	return Ftp().ftpDisableUser(user)
def ftpEnableUser(user):
	return Ftp().ftpEnableUser(user)

# Read ini configuration
class FtpConfig(PluginConfig):

	def readConf(self):
		PluginConfig.readConf(self)
	        try: self.path = self.get("main", "shorewall_path")
	        except (NoSectionError, NoOptionError): self.path = "/etc/shorewall"
class LdapConfig(PluginConfig):
	def readConf(self):
		PluginConfig.readConf(self)
		try: self.host = self.get("ldap", "host")
		except (NoSectionError, NoOptionError): self.host = "127.0.0.1"
		try: self.root = self.get("ldap", "rootName")
		except (NoSectionError, NoOptionError): self.root = "uid=LDAP Admin, ou=System Accounts, dc=localdomain"

		self.passw = self.get("ldap", "password")

		try: self.userdn = self.get("ldap", "baseUsersDN")
		except (NoSectionError, NoOptionError): self.userdn = "ou=People, dc=localdomain"

		try: self.groupdn = self.get("ldap", "baseGroupsDN")
		except (NoSectionError, NoOptionError): self.groupdn = "ou=Group, dc=localdomain"
