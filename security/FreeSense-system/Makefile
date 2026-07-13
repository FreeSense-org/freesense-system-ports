PORTNAME=	FreeSense-system
DISTVERSION=	${PRODUCT_VERSION}
DISTVERSIONPREFIX=	v
CATEGORIES=	security

MAINTAINER=	dev@freesense.org
COMMENT?=	FreeSense system package
WWW=	https://freesense.org/

LICENSE=	APACHE20

RUN_DEPENDS=	bind-tools>=0:dns/bind-tools \
		bsnmp-regex>=0:net-mgmt/bsnmp-regex \
		bsnmp-ucd>=0:net-mgmt/bsnmp-ucd \
		ca_root_nss>=0:security/ca_root_nss \
		check_reload_status>=0:sysutils/check_reload_status \
		choparp>=0:net-mgmt/choparp \
		cpdup>=0:sysutils/cpdup \
		cpustats>=0:sysutils/cpustats \
		dhcp6>=0:net/dhcp6 \
		dhcpcd>0:net/dhcpcd \
		dhcpleases>=0:sysutils/dhcpleases \
		dhcpleases6>=0:sysutils/dhcpleases6 \
		dnsmasq>=0:dns/dnsmasq \
		dpinger>=0:net/dpinger \
		expiretable>=0:security/expiretable \
		filterdns>=0:net/filterdns \
		filterlog>=0:sysutils/filterlog \
		hostapd>=0:net/hostapd \
		igmpproxy>=0:net/igmpproxy \
		ipmitool>=0:sysutils/ipmitool \
		isc-dhcp44-client>=0:net/isc-dhcp44-client \
		isc-dhcp44-relay>=0:net/isc-dhcp44-relay \
		isc-dhcp44-server>=0:net/isc-dhcp44-server \
		jq>0:textproc/jq \
		kea>0:net/kea \
		libxml2>=0:textproc/libxml2 \
		links>=0:www/links \
		minicron>=0:sysutils/minicron \
		miniupnpd>=0:net/miniupnpd \
		mobile-broadband-provider-info>=0:net/mobile-broadband-provider-info \
		mpd5>=0:net/mpd5 \
		nginx>=0:www/nginx \
		ntp>=0:net/ntp \
		openvpn>=0:security/openvpn \
		${PHP_PKGNAMEPREFIX}openssl_x509_crl>=0:security/php-openssl_x509_crl@${PHP_FLAVOR} \
		${PHP_PKGNAMEPREFIX}pear-Auth_RADIUS>=0:net/pear-Auth_RADIUS@${PHP_FLAVOR} \
		${PHP_PKGNAMEPREFIX}pear-Crypt_CHAP>=0:security/pear-Crypt_CHAP@${PHP_FLAVOR} \
		${PHP_PKGNAMEPREFIX}pear-Mail>=0:mail/pear-Mail@${PHP_FLAVOR} \
		${PHP_PKGNAMEPREFIX}pear-Net_IPv6>=0:net/pear-Net_IPv6@${PHP_FLAVOR} \
		${PHP_PKGNAMEPREFIX}pear-XML_RPC2>=0:net/pear-XML_RPC2@${PHP_FLAVOR} \
		${PHP_PKGNAMEPREFIX}FreeSense-module>=0:devel/php-FreeSense-module@${PHP_FLAVOR} \
		${PHP_PKGNAMEPREFIX}phpseclib>=0:security/phpseclib@${PHP_FLAVOR} \
		FreeSense-Status_Monitoring${PHP_PKGNAMESUFFIX}>=0:sysutils/FreeSense-Status_Monitoring@${PHP_FLAVOR} \
		FreeSense-composer-deps>=0:devel/FreeSense-composer-deps \
		FreeSense-upgrade>=0:sysutils/FreeSense-upgrade \
		pftop>=0:sysutils/pftop \
		qstats>=0:sysutils/qstats \
		radvd>=0:net/radvd \
		rate>=0:net-mgmt/rate \
		scponly>=0:shells/scponly \
		smartmontools>=0:sysutils/smartmontools \
		ssh_tunnel_shell>=0:sysutils/ssh_tunnel_shell \
		sshguard>=0:security/sshguard \
		strongswan>=0:security/strongswan \
		uclcmd>=0:devel/uclcmd \
		unbound>=0:dns/unbound \
		voucher>=0:sysutils/voucher \
		wol>=0:net/wol \
		wpa_supplicant>=0:security/wpa_supplicant \
		whois>0:net/whois \
		xinetd>=0:security/xinetd \
		openvpn-auth-script>=0:security/openvpn-auth-script \
		opensc>0:security/opensc \
		libccid>0:devel/libccid \
		iftop>0:net-mgmt/iftop \
		nss_ldap>0:net/nss_ldap \
		pam_ldap>0:security/pam_ldap \
		pam_mkhomedir>0:security/pam_mkhomedir

LIB_DEPENDS=	libltdl.so:devel/libltdl

USES=		php:flavors

IGNORE_WITH_PHP=	72 73 74 80 81 82 83 84
USE_PHP=	bz2 bcmath ctype curl dom filter gettext gmp intl json mbstring \
		mcrypt opcache openssl pcntl pdo pdo_sqlite posix \
		radius readline session shmop simplexml sockets sysvmsg sysvsem \
		sysvshm sqlite3 tokenizer xml ldap zlib xmlreader xmlwriter

NO_BUILD=	yes

CONFLICTS=	FreeSense-vmware-[0-9]*

# FreeSense: build the base system from our locally-staged rebranded source
# tarball (tools/ci/sync-freesense.sh produces /usr/ports/distfiles/freesense-src.tar.gz)
# instead of fetching from inaccessible vendor infrastructure that the
# upstream pfSense-system port uses.
DISTFILES=	freesense-src.tar.gz
WRKSRC=		${WRKDIR}/freesense-src
MASTER_SITE_BACKUP=
NO_CHECKSUM=yes

SUB_FILES=	pkg-post-install
SUB_LIST=	PRODUCT_NAME=${PRODUCT_NAME}
PKGPOSTINSTALL=	${WRKDIR}/pkg-post-install
DATADIR=	${PREFIX}/share/FreeSense

.include <bsd.port.pre.mk>

.if ${ARCH} == "amd64"
# bwi-firmware-kmod (Broadcom BCM43xx wifi firmware) dropped: out-of-tree kmods
# don't build against the pinned 16-CURRENT snapshots, and it's museum hardware
# for a firewall. Re-add if the port catches up and anyone actually needs it.
RUN_DEPENDS+=	dmidecode>=0:sysutils/dmidecode \
		wrapalixresetbutton>=0:sysutils/wrapalixresetbutton \
		beep>=0:audio/beep \
		cpu-microcode>=0:sysutils/cpu-microcode
.endif

do-install:
	(cd ${WRKSRC}/src && ${COPYTREE_SHARE} "etc usr" ${STAGEDIR})
	${MKDIR} "${STAGEDIR}/cf/conf"

.include <bsd.port.post.mk>
