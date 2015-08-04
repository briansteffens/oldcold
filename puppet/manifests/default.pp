Exec { path => [ "/bin/", "/sbin/" , "/usr/bin/", "/usr/sbin/" ] }

exec { 'apt-get update':
    command => 'apt-get update',
}

package { "squid-deb-proxy-client":
    ensure  => present,
    require => Exec["apt-get update"],
}

package { ["python3", "libpython3-dev", "python3-pip"]:
    ensure  => present,
    require => Package["squid-deb-proxy-client"],
}

exec { 'cherrypy':
    command => 'pip3 install cherrypy',
    require => Package['python3-pip'],
}

file { '/etc/cold':
    ensure => 'directory',
}

file { "/etc/cold/server.conf":
    ensure => 'link',
    target => '/vagrant/vagrant/server.conf',
    require => File['/etc/cold'],
}

file { '/etc/cold/node.conf':
    ensure => 'link',
    target => '/vagrant/vagrant/node.conf',
    require => File['/etc/cold'],
}
