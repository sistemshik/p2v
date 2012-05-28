#!/usr/bin/python
"""Script for making dumps from virtual servers and restoring it to VM's"""

import sys
import ConfigParser
import os.path 
import subprocess 

def read_config(server):
    """Reads config file specifying how to work with servers
    and returns dictionary with configuration"""

    print "\nREADING CONFIG FOR %r\n" % server
    config = ConfigParser.ConfigParser()
    config.read('p2v.cfg')
    dumps_list = config.get(server, 'dumps_list').rsplit(',')

    conf = { 'name':        server,
             'vm_config':   config.get(server, 'vm_config',  0),
             'vm_name':     config.get(server, 'vm_name',    0),
             'ssh':         config.get(server, 'ssh',        0),            # how to ssh to remote server
             'scp':         config.get(server, 'scp',        0),            # how to scp to remote server
             'dumps_list':  dumps_list,                                     # what to dump 
             'remote_dumps_dir':  config.get(server, 'remote_dumps_dir', 0),      # where to store dumps remotely
             'local_dumps_dir':   config.get(server, 'local_dumps_dir',  0),      # where to store dumps locally
             'partition':   config.get(server, 'partition',  0),            # which parition to use for vm 
             'mount_dir':   config.get(server, 'mount_dir',  0),            # where to mount vm's parititon
             'fs':          config.get(server, 'fs', 0)}                    # what fs to make

    print "\nMY CONFIG IS: %r\n" % conf
    return conf

def check_config_local(conf):
    """Checks config by trying to ssh, checking existence of local and remote folders,
    destination partition, mount point, and remote dump utility""" 

    print "\nCHECKING LOCAL CONFIG\n"

    # check for ensuring we won't delete accidentaly specified host os parittion
    if conf['partition'] == "/dev/sda"  or conf['partition'] == "/dev/sda1" or \
       conf['partition'] == "/dev/sda2" or conf['partition'] == "/dev/sda3" or \
       conf['partition'] == "/dev/sda4" or conf['partition'] == "/dev/sda5":
        raise Exception, "DON'T KILL THE SERVER! %S IS A SYSTEM PARTITION!!" % conf['partition']

    # check if all paths exist
    if not os.path.exists(conf['local_dumps_dir']):
        raise Exception, "LOCAL_DUMPS_DIR DOES NOT EXIST: %r" % conf['local_dumps_dir']
    if not os.path.exists("%s/%s" % (conf['local_dumps_dir'], 'cfg')):
        raise Exception, "LOCAL_DUMPS_DIR/CFG DOES NOT EXIST: %r/%r" % (conf['local_dumps_dir'], 'cfg')
    if not os.path.exists(conf['mount_dir']):
        raise Exception, "MOUNT_DIR DOES NOT EXIST: %r" % conf['mount_dir']
    
    # check if vm config is abailable
    if not os.path.exists(conf['vm_config']):
        raise Exception, "CONFIG FOR VM DOES NOT EXIST: %r" % conf['vm_config']

    # check if vm name is specified correctly
    vm_name_ok = False
    vm_config = open(conf['vm_config'], 'r')
    for line in vm_config:
        params = line.split('=')
        if params[0].strip(' ') == "name":
            if params[1].strip(' "\n"') == conf['vm_name']:
                vm_name_ok = True
    vm_config.close()

    if not vm_name_ok: 
        raise Exception, "VM NAME: %r DOES NOT EXIST IN CONFIG: %r" % (conf['vm_name'], conf['vm_config'])

    # check if mount point is available
    if os.path.ismount(conf['mount_dir']):
        raise Exception, "MOUNT_DIR IS ALREADY MOUNTED: %r" % conf['mount_dir']

    # check if parition exists
    if not os.path.exists(conf['partition']):
        raise Exception, "PARTITION DOES NOT EXIST: %r" % conf['partition']

    print "\nCHECKING LOCAL CONFIG FOR %r COMPLETED SUCCESSFULLY\n" % conf['name']

def check_config_remote(conf):
    """Cheks if we are able to perform or desired operations on remote server"""
    print "\nCHECKING REMOTE CONFIG\n"

    # check if we are able to ssh and if remote directory exist
    check_dir = "if [ -d %s ] ; then exit 0 ; else exit 1 ; fi" % conf['remote_dumps_dir']
    ssh = "ssh -T %s '%s'" % (conf['ssh'], check_dir)
    print "\nCHECKING IF WE ARE ABLE TO SSH TO: %r\n" % ssh

    if subprocess.call(ssh, shell=True) != 0:
        raise Exception, "Somthing went wrong when checking existence of remore directory: %r" % ssh

    # check if remote directory has nodump flag set
    # does the following: lsattr -d /data/dumps | egrep '[\w-]+d[\w-]+[ ]/data/dumps' 
    lsattr = "lsattr -d %s | egrep '[\w-]+d[\w-]+[ ]%s'" % (conf['remote_dumps_dir'], conf['remote_dumps_dir'])
    ssh = "ssh -T %s \"%s\"" % (conf['ssh'], lsattr)
    print "\nCHECKING NODUMP FLAG: %r\n" % lsattr

    if subprocess.call(ssh, shell=True) != 0:
        raise Exception, "Somthing is wrong when checking nodump flag: %r" % ssh

    # check if we are able to execute dump remotely
    dump = "sudo /sbin/dump a0f /dev/null /dev/null"
    ssh = "ssh -T %s %s" % (conf['ssh'], dump)
    print "\nCHECKING REMOTE DUMP: %r\n" % dump 

    if subprocess.call(ssh, shell=True) != 0:
        raise Exception, "Somthing is wrong when tried to execute dump remotely: %r" % ssh
    
    # check if all remote mount points from config file exist and are really mount point
    for item in conf['dumps_list']:

        print "\nCHECKING REMOTE PARTITION: %r\n" % item
        mount = "grep '%s' /proc/mounts" % item
        ssh = "ssh -T %s %s" % (conf['ssh'], mount)

        if subprocess.call(ssh, shell=True) != 0:
            raise Exception, "Somthing is wrong when checking filesystems for dumping: %r" % ssh

    print "\nCHECKING REMOTE CONFIG FOR %r COMPLETED SUCCESSFULLY\n" % conf['name']

def dump_physical(conf):
    """Makes dumps from specified server"""

    print "\nDUMPING FOLLOWING FILESYSTEMS: %r\n" % conf['dumps_list']

    for item in conf['dumps_list']:

        if item == '/':
            file = conf['name'] + '.root'
        else:
            file = conf['name'] + '.' + item.strip('/')

        ssh = "ssh -T %s sudo dump -h0 -ua0f %s/%s %s" % ( conf['ssh'], conf['remote_dumps_dir'], file, item)

        if subprocess.call(ssh, shell=True) != 0:
            raise Exception, "ERROR IN: %r" % restore

def get_dumps(conf):
    """Copies dumps to local storage"""

    print "\nGETTING THE FOLLOWING DUMPS: %r\n" % conf['dumps_list']

    for item in conf['dumps_list']:

        if item == '/':
            file = conf['name'] + '.root'
        else:
            file = conf['name'] + '.' + item.strip('/')

        scp = "scp -C %s:%s/%s %s " % (conf['scp'], conf['remote_dumps_dir'], file, conf['local_dumps_dir'])

        if subprocess.call(scp, shell=True) != 0:
            raise Exception, "ERROR IN: %r" % restore

def mkfs(conf):
    """Make filesystem for VM"""

    print "\nMAKING FS TYPE: %s ON PARTITION: %s \n" % (conf['fs'], conf['partition'])
    mkfs = "mkfs -t %s %s" % (conf['fs'], conf['partition'])

    if subprocess.call(mkfs, shell=True) != 0:
        raise Exception, "ERROR IN: %r" % mkfs
        
def restore_vm(conf):
    """Restores dumps to specified VM"""

    mount(conf)
    print "\nRESTORING DUMPS FOR: %s\n" % conf['name']
    for item in conf['dumps_list']:

        if item == '/':
            file = conf['name'] + '.root'
        else:
            file = conf['name'] + '.' + item.strip('/')

        restore = "cd %s/%s && restore -rf %s/%s" % ( conf['mount_dir'], item, conf['local_dumps_dir'], file)

        if subprocess.call(restore, shell=True) != 0:
            raise Exception, "ERROR IN: %r" % restore

    umount(conf)

def install_bootloader(conf):
    """Installs selinux bootloader"""
    
    print "\nINSTALLING BOOTLOADER FOR: %s\n" % conf['name']
    mount(conf)

    if not os.path.ismount(conf['mount_dir']):
        raise Exception, "mount_dir is already mounted, unmounting: %r" % conf['mount_dir']

    mbr = "dd if=/usr/share/syslinux/mbr.bin of=%s" % conf['partition'] 

    if subprocess.call(mbr, shell=True) != 0:
        raise Exception, "ERROR IN: %r" % mbr

    extlinux = "extlinux --install %s" % conf['mount_dir']

    if subprocess.call(extlinux, shell=True) != 0:
        raise Exception, "ERROR IN: %r" % extlinux

    umount(conf)

def restore_config(conf):
    """Copies configs for given vm, overwriting existing ones"""

    print "\nRESTORING CONFIG FOR: %s\n" % conf['name']
    mount(conf)
    cp = "cp -R %s/cfg/* %s" % (conf['local_dumps_dir'], conf['mount_dir']) 

    if subprocess.call(cp, shell=True) != 0:
        raise Exception, "ERROR IN: %r" % cp

    umount(conf)

def start_vm(conf):
    """Starts given vm"""
    print "\nSTARTING VM: %s\n" % conf['vm_config']
    xm_create = "xm create %s" % conf['vm_config']

    if subprocess.call(xm_create, shell=True) != 0:
        raise Exception, "ERROR IN: %r" % xm_create

def stop_vm(conf):
    """Stops given vm"""
    print "\nSTOPPING VM : %s\n" % conf['vm_name']
    xm_destroy = "xm destroy %s" % conf['vm_name']

    if subprocess.call(xm_destroy, shell=True) != 0:
        print "ERROR IN: %r, VM IS NOT RUNNING. CONTINUING ANYWAY." % xm_destroy

def mount(conf):
    """mounts partition"""
    mount = "mount %s %s" % (conf['partition'], conf['mount_dir'])

    if subprocess.call(mount, shell=True) != 0:
        raise Exception, "ERROR IN: %r" % mount
 
def umount(conf):
    """unmounts partition"""
    umount = "umount %s" % (conf['mount_dir'])

    if subprocess.call(umount, shell=True) != 0:
        raise Exception, "ERROR IN: %r" % umount

def cleanup(conf):
    """Cleans up on exception, that is unmouts partition"""

    if os.path.ismount(conf['mount_dir']):
        umount(conf)

def main():
    """Main function, calls all other ones"""

    if len(sys.argv) < 3:
        sys.exit('Usage: %s <servername> <action> (check|dump|restore|full)' % sys.argv[0])

    server = sys.argv[1]
    action = sys.argv[2]

    print "\nWORKING WITH SERVER: %r\n" % server
    
    if action == "check":
        try:
            conf=read_config(server)
            check_config_local(conf)
            check_config_remote(conf)
        except Exception, e:
            #sys.exit("Execution failed: %r\n%r" % (e, sys.exc_info()))
            sys.exit("\nERROR: %r\n" % e)
    elif action == "full":
        try:
            conf=read_config(server)
            check_config_local(conf)
            check_config_remote(conf)
            stop_vm(conf)
            mkfs(conf)
            dump_physical(conf)
            get_dumps(conf)
            restore_vm(conf)
            install_bootloader(conf)
            restore_config(conf)
            start_vm(conf)
        except Exception, e:
            cleanup(conf)
            sys.exit("\nERROR: %r\n" % e)
    elif action == "restore":
        try:
            conf=read_config(server)
            check_config_local(conf)
            stop_vm(conf)
            mkfs(conf)
            restore_vm(conf)
            install_bootloader(conf)
            restore_config(conf)
            start_vm(conf)
        except Exception, e:
            cleanup(conf)
            sys.exit("\nERROR: %r\n" % e)
    elif action == "dump":
        try:
            conf=read_config(server)
            check_config_local(conf)
            check_config_remote(conf)
            dump_physical(conf)
            get_dumps(conf)
        except Exception, e:
            cleanup(conf)
            sys.exit("\nERROR: %r\n" % e)
    elif action == "test":
        try:
            pass
        except Exception, e:
            sys.exit("\nERROR: %r\n" % e)

main()
