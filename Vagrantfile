# -*- mode: ruby -*-
# vi: set ft=ruby :

# This Vagrantfile will spin up a CentOS 6 box with Asterisk installed
# from Digium's AsteriskNOW repository.

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "nrel/CentOS-6.5-x86_64"

  # You can attach softphones via this network.
  config.vm.network :private_network, ip: "172.20.64.100"

  # Bridge to a physical network if you want to attach physical phones.
  # Beware, though: the VM won't be firewalled!
  #
  # I've specified 'ASK' to force Vagrant to ask you for the interface
  # you want to use.
  #config.vm.network :public_network, ip: "172.25.75.100", :bridge => 'ASK'

  config.vm.provision :ansible do |ansible|
    ansible.playbook = "etc/playbook.yml"
  end

end
