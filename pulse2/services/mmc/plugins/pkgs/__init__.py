#
# (c) 2004-2007 Linbox / Free&ALter Soft, http://linbox.com
# (c) 2007-2008 Mandriva
#
# $Id$
#
# This file is part of MMC.
#
# MMC is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# MMC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MMC; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging
import os, shutil
import requests, json, tempfile, tarfile
from ConfigParser import ConfigParser
from base64 import b64encode, b64decode
from time import time

from mmc.site import mmcconfdir
from mmc.support.mmctools import RpcProxyI, ContextMakerI, SecurityContext
from mmc.core.tasks import TaskManager

from mmc.plugins.msc.package_api import PackageGetA
from mmc.plugins.pkgs.package_put_api import PackagePutA
from mmc.plugins.pkgs.user_packageapi_api import UserPackageApiApi
from mmc.plugins.pkgs.config import PkgsConfig

from pulse2.version import getVersion, getRevision # pyflakes.ignore

APIVERSION = "0:0:0"

def getApiVersion(): return APIVERSION

def activate():
    logger = logging.getLogger()
    logger.debug("Pkgs is activating")
    config = PkgsConfig("pkgs")
    if config.disabled:
        logger.warning("Plugin pkgs: disabled by configuration.")
        return False
    
    TaskManager().addTask("pkgs.updateAppstreamPackages",
                        (updateAppstreamPackages,),
                        cron_expression='23 10 * * *')
    return True

class ContextMaker(ContextMakerI):
    def getContext(self):
        s = SecurityContext()
        s.userid = self.userid
        return s

class ConfigReader(object):
    """Read and parse config files"""
    def __init__(self):
        agent_ini = os.path.join(mmcconfdir, 
                                "agent", 
                                "config.ini")
        self._agent_config = self.get_config(agent_ini)


    @classmethod
    def get_config(cls, inifile):
        """
        Get the configuration from config file

        @param inifile: path to config file
        @type inifile: string

        @return: ConfigParser.ConfigParser instance 
        """
        logging.getLogger().debug("Load config file %s" % inifile)
        if not os.path.exists(inifile) :
            logging.getLogger().error("Error while reading the config file: Not found.")
            return False

        config = ConfigParser()
        config.readfp(open(inifile))
        if os.path.isfile(inifile + '.local'):
            config.readfp(open(inifile + '.local','r'))

        return config

    @property
    def agent_config(self):
        """ 
        Get the configuration of package server 

        @return: ConfigParser.ConfigParser instance 
        """
        return self._agent_config

class RpcProxy(RpcProxyI):
    def getPApiDetail(self, pp_api_id):
        def _getPApiDetail(result, pp_api_id = pp_api_id):
            for upa in result: 
                if upa['uuid'] == pp_api_id:
                    return upa
            return False
        
        d = self.upaa_getUserPackageApi()
        d.addCallback(_getPApiDetail)
        return d

    # PackagePutA
    def ppa_getPackageDetail(self, pp_api_id, pid):
        def _ppa_getPackageDetail(result, pp_api_id = pp_api_id, pid = pid):
            for upa in result:
                if upa['uuid'] == pp_api_id:
                    return PackageGetA(upa).getPackageDetail(pid)
            return False
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_getPackageDetail)
        return d

    def ppa_pushPackage(self, pp_api_id, random_dir, files, local_mmc):
        def _ppa_pushPackage(result, pp_api_id = pp_api_id, random_dir = random_dir, files = files, local_mmc = local_mmc):
            def _encodeFiles(random_dir, files):
                encoded_files = []
                for file in files:
                    logging.getLogger().debug("Encoding file %s" % file['filename'])
                    tmp_dir = file['tmp_dir']
                    f = open(os.path.join(tmp_dir, random_dir, file['filename']), 'r')
                    encoded_files.append({
                        'filename': file['filename'],
                        'filebinary': b64encode(f.read()),
                    })
                    f.close()
                return encoded_files

            def _decodeFiles(random_dir, files):
                pkgs_tmp_dir = self.getPServerTmpDir()
                if not os.path.exists(os.path.join(pkgs_tmp_dir, random_dir)):
                    os.makedirs(os.path.join(pkgs_tmp_dir, random_dir))
                filepath = os.path.join(pkgs_tmp_dir, random_dir)
                for file in files:
                    logging.getLogger().debug("Decoding file %s" % file['filename'])
                    f = open(os.path.join(filepath, file['filename']), 'w')
                    f.write(b64decode(file['filebinary']))
                    f.close()
                    file['filebinary'] = False
                    file['tmp_dir'] = pkgs_tmp_dir
                return files

            for upa in result:
                if upa['uuid'] == pp_api_id:
                    local_pserver = self.getPServerIP() in ['localhost', '127.0.0.1'] and True or False
                    if local_mmc:
                        logging.getLogger().info("Push package from local mmc-agent...")
                        if local_pserver:
                            logging.getLogger().info("... to local package server")
                            return PackagePutA(upa).pushPackage(random_dir, files, local_pserver)
                        else:
                            logging.getLogger().info("... to external package server")
                            # Encode files (base64) and send them with XMLRPC
                            encoded_files = _encodeFiles(random_dir, files)
                            return PackagePutA(upa).pushPackage(random_dir, encoded_files, local_pserver)
                    else:
                        logging.getLogger().info("Push package from external mmc-agent...")
                        if local_pserver:
                            logging.getLogger().info("... to local package server")
                            # decode files
                            decoded_files = _decodeFiles(random_dir, files)
                            return PackagePutA(upa).pushPackage(random_dir, decoded_files, local_pserver)
                        else:
                            logging.getLogger().info("... to external package server")
                            return PackagePutA(upa).pushPackage(random_dir, files, local_pserver)
            logging.getLogger().warn("Failed to push package on %s"%(pp_api_id))
            return False
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_pushPackage)
        return d

    def ppa_putPackageDetail(self, pp_api_id, package, need_assign = True):
        def _ppa_putPackageDetail(result, pp_api_id = pp_api_id, package = package, need_assign = need_assign):
            for upa in result:
                if upa['uuid'] == pp_api_id:
                    return PackagePutA(upa).putPackageDetail(package, need_assign)
            logging.getLogger().warn("Failed to put package details on %s"%(pp_api_id))
            return False
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_putPackageDetail)
        return d

    def ppa_dropPackage(self, pp_api_id, pid):
        logging.getLogger().info('I will drop package %s/%s' % (pp_api_id, pid))
        def _ppa_dropPackage(result, pp_api_id = pp_api_id, pid = pid):
            for upa in result:
                if upa['uuid'] == pp_api_id:
                    return PackagePutA(upa).dropPackage(pid)
            return False
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_dropPackage)
        return d

    def ppa_getTemporaryFiles(self, pp_api_id):
        def _ppa_getTemporaryFiles(result, pp_api_id = pp_api_id):
            for upa in result:
                if upa['uuid'] == pp_api_id:
                    return PackagePutA(upa).getTemporaryFiles()
            return []
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_getTemporaryFiles)
        return d

    def ppa_getTemporaryFileSuggestedCommand(self, pp_api_id, tempdir):
        def _ppa_getTemporaryFilesSuggestedCommand(result, pp_api_id = pp_api_id, tempdir = tempdir):
            for upa in result:
                if upa['uuid'] == pp_api_id:
                    return PackagePutA(upa).getTemporaryFilesSuggestedCommand(tempdir)
            return []
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_getTemporaryFilesSuggestedCommand)
        return d

    def ppa_associatePackages(self, pp_api_id, pid, files, level = 0):
        def _ppa_associatePackages(result, pp_api_id = pp_api_id, pid = pid, files = files, level = level):
            for upa in result:
                if upa['uuid'] == pp_api_id:
                    return PackagePutA(upa).associatePackages(pid, files, level)
            return []
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_associatePackages)
        return d
    
    
    def ppa_removeFilesFromPackage(self, pp_api_id, pid, files):
        def _ppa_removeFilesFromPackage(result, pp_api_id = pp_api_id, pid = pid, files = files):
            for upa in result:
                if upa['uuid'] == pp_api_id:
                    return PackagePutA(upa).removeFilesFromPackage(pid, files)
            return []
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_removeFilesFromPackage)
        return d

    def ppa_getRsyncStatus(self, pp_api_id, pid):
        def _ppa_getRsyncStatus(result, pp_api_id = pp_api_id, pid = pid):
            for upa in result:
                if upa['uuid'] == pp_api_id:
                    return PackagePutA(upa).getRsyncStatus(pid)
            return []
        d = self.upaa_getUserPackageApi()
        d.addCallback(_ppa_getRsyncStatus)
        return d
    
    # UserPackageApiApi
    def upaa_getUserPackageApi(self):
        ctx = self.currentContext
        return UserPackageApiApi().getUserPackageApi(ctx.userid)

    def getMMCIP(self):
        config = ConfigReader()

        self.agent_config = config.agent_config

        return self.agent_config.get("main", "host")

    def getPServerIP(self):
        config = PkgsConfig("pkgs")
        return config.upaa_server

    def getPServerTmpDir(self):
        config = PkgsConfig("pkgs")
        return config.tmp_dir
    

def get_installation_uuid():
    return open('/etc/pulse-licensing/installation_id').read().strip()

def lserv_query(cmd, options):
    settings = getAppstreamJSON()
    try:
        my_username = settings['my_username']
        my_password = settings['my_password']
    except KeyError:
        return -1

    url = 'https://activation.mandriva.com/' + cmd
    headers = {'content-type': 'application/json'}
    r = requests.get(\
                     url,
                     data=json.dumps(options),
                     headers=headers,
                     auth=(my_username, my_password)
                     )
    return json.loads(r.content)
    
def getAppstreamJSON():
    try:
        return json.loads(open('/etc/mmc/plugins/appstream.json').read())
    except:
        return {}

def setAppstreamJSON(data):
    try:
        f = open("/etc/mmc/plugins/appstream.json", "w")
        f.write(json.dumps(data))
        f.close()
        return True
    except Exception, e:
        logging.getLogger().error('Cannot write appstream JSON')
        logging.getLogger().error(str(e))
        return False
        

def getActivatedAppstreamPackages():
    json = getAppstreamJSON()
    if 'flows' in json:
        return json['flows']
    else:
        return {}

def getAvailableAppstreamPackages():
    return lserv_query('auth/customer/', {
        'name_licence' : 'appstream',
        'gui_product' : '-'
    })

def activateAppstreamFlow(id, package_name, package_label, duration):
    result = lserv_query('activate/licencing/', {
        'name_licence' : 'appstream',
        'gui_product' : get_installation_uuid(),
        'id' : id,
        'keypublique' : '=',
        'keysshpublique' : '='
    })
    key = result['licence'].strip()
    
    # Add key to appStream JSON
    json = getAppstreamJSON()
    if not 'flows' in json:
        json['flows'] = {}
        
    json['flows'][package_name] = {
        'id':id,
        'key':key,
        'label':package_label,
        'expiration_ts':int(time()) + int(duration) * 30.5 * 24 * 3600
    }
    setAppstreamJSON(json)
    updateAppstreamPackages()
    return True

def updateAppstreamPackages():
    
    tempfile.tempdir='/var/tmp/'
    logger = logging.getLogger()
    appstream_url = PkgsConfig("pkgs").appstream_url
    
    for pkg, info in getActivatedAppstreamPackages().iteritems():
        
        try:
            # Creating requests session
            s = requests.Session()
            s.auth = ('appstream', info['key'])
            base_url = '%s/%s/' % (appstream_url, pkg)
            package_dir = None
            
            # Get Package uuid
            r = s.get(base_url + 'uuid')
            if not r.ok:
                raise Exception("Cannot get package metadata (uuid). Status: %d" % (r.status_code))
            uuid = r.content.strip()
            
            # If package is already downloaded, skip
            if not uuid or os.path.exists('/var/lib/pulse2/appstream_packages/%s/' % uuid):
                continue
            
            # Creating package directory
            package_dir = '/var/lib/pulse2/appstream_packages/%s/' % uuid
            os.mkdir(package_dir)
            
            # Get third party downloads
            r = s.get(base_url + 'downloads')
            if not r.ok:
                raise Exception("Cannot get package metadata (downloads). Status: %d" % (r.status_code))
            
            # Downloading third party binaries
            downloads = r.content.strip()
            for line in downloads.split('\n'):
                filename, url = line.split(';')
                # Downloading file
                with open(package_dir+filename, 'wb') as handle:
                    r = s.get(url, prefetch=False)
                    
                    if not r.ok:
                        raise Exception("Cannot download third party files. Status: %d" % (r.status_code))
                    
                    for block in r.iter_content(1024):
                        if not block:
                            break
                        handle.write(block)
            
            # Download data file
            data_temp_file = tempfile.mkstemp()[1]
            with open(data_temp_file, 'wb') as handle:
                # Important: For newer versions of python-requests, use stream=True instead of prefetch
                r = s.get(base_url + 'data.tar.gz', prefetch=False)
            
                if not r.ok:
                    raise Exception("Cannot download package data. Status: %d" % r.status_code)
                
                for block in r.iter_content(1024):
                    if not block:
                        break
                    handle.write(block)
                    
            # Extracting data archive
            tar = tarfile.open(data_temp_file)
            tar.extractall(path=package_dir)
            tar.close()
            
            # Removing tempfile
            os.remove(data_temp_file)
        
        except Exception, e:
            logger.error('Appstream: Error while fetching package %s' % pkg)
            logger.error(str(e))
            
            # Removing package dir (if exists)
            try:
                shutil.rmtree(package_dir)
            except Exception, e:
                logger.error(str(e))

    return True
