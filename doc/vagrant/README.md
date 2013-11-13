Vagrant hacking setup
====

If you're interested in a virtual environment for hacking on
`octothorpe`, I've supplied here my [Vagrant][1] and [Ansible][2]
configurations for building and doing the initial configuration for
a box with Asterisk running and ready to accept a SIP phone connection.

You will need a CentOS 6 box to start.  I grabbed the latest
`CentOS-6.4-x86_64` box from
http://developer.nrel.gov/downloads/vagrant-boxes/ for this purpose.
`vagrant add box centos6 http://...` is your friend here, substituting
the `...` for something useful of course.

Put `Vagrantfile`, `playbook.yml`, and `etc` (containing the Asterisk
configurations) in the same directory, and run `vagrant up` to start
your system.  Pay close attention to `Vagrantfile`—it contains a
directive for setting up a host-only network.  I've randomly selected
an RFC1918 address for this purpose; you'll want to connect your SIP
softphone and your `octothorpe` applications to this address.

**Note:** the current Ansible playbook has a bit of hackishness to it,
as I needed to make use of a feature (replacing a directory with a
symlink) in Ansible's development version that is not present in
the current 1.3 release series.  Said hack is commented, and I
assume it will work with the development version.  In the meantime,
it also works with what `pip install ansible` gives you today.

**Even More Important Note:** Don't even *think* of using the config
files in `etc/asterisk` in production!  They are wildly insecure.

[1]: http://vagrantup.com/
[2]: http://ansibleworks.com/

