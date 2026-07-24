PORTNAME=	FreeSense-upgrade
PORTVERSION=	1.3.25
# FreeSense: bumped to force a rebuild after patching files/. PORTVERSION is
# fixed, so every shipped script correction must advance PORTREVISION.
PORTREVISION=	6
CATEGORIES=	sysutils
MASTER_SITES=	# empty
DISTFILES=	# empty
EXTRACT_ONLY=	# empty

MAINTAINER=	dev@freesense.org
COMMENT=	FreeSense upgrade script

LICENSE=	APACHE20

NO_MTREE=	yes
NO_BUILD=	yes

PLIST_FILES=	libexec/install-boot.sh \
		libexec/FreeSense-upgrade \
		sbin/freesense-be \
		sbin/freesense-zfs-status \
		etc/rc.d/freesense_be_health \
		sbin/install-boot \
		sbin/FreeSense-repo-setup \
		sbin/FreeSense-upgrade

.include <bsd.port.pre.mk>


do-extract:
	@${MKDIR} ${WRKSRC}
	${CP} -r ${FILESDIR}/* ${WRKSRC}

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/sbin
	${MKDIR} ${STAGEDIR}${PREFIX}/libexec
	${MKDIR} ${STAGEDIR}${PREFIX}/share/FreeSense
	${INSTALL_SCRIPT} ${WRKSRC}/FreeSense-repo-setup \
		${STAGEDIR}${PREFIX}/sbin
	${INSTALL_SCRIPT} ${WRKSRC}/FreeSense-upgrade \
		${STAGEDIR}${PREFIX}/libexec
	${INSTALL_SCRIPT} ${WRKSRC}/FreeSense-upgrade.wrapper \
		${STAGEDIR}${PREFIX}/sbin/FreeSense-upgrade
	${INSTALL_SCRIPT} ${WRKSRC}/install-boot \
		${STAGEDIR}${PREFIX}/sbin
	${INSTALL_SCRIPT} ${WRKSRC}/install-boot.sh \
		${STAGEDIR}${PREFIX}/libexec
	${INSTALL_SCRIPT} ${WRKSRC}/freesense-be \
		${STAGEDIR}${PREFIX}/sbin
	${INSTALL_SCRIPT} ${WRKSRC}/freesense-zfs-status \
		${STAGEDIR}${PREFIX}/sbin
	${MKDIR} ${STAGEDIR}${PREFIX}/etc/rc.d
	${INSTALL_SCRIPT} ${WRKSRC}/freesense_be_health \
		${STAGEDIR}${PREFIX}/etc/rc.d

.include <bsd.port.post.mk>
