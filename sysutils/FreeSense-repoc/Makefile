PORTNAME=	repoc
PORTVERSION=	1.0.0
# Script-only port: advance this whenever files/ changes so installed systems
# receive the corrected repository client during an ordinary pkg upgrade.
PORTREVISION=	6
CATEGORIES=	sysutils
PKGNAMEPREFIX=	FreeSense-
MASTER_SITES=	# empty
DISTFILES=	# empty
EXTRACT_ONLY=	# empty

MAINTAINER=	dev@freesense.org
COMMENT=	FreeSense static repository client

LICENSE=	APACHE20

# FreeSense: this REPLACES Netgate's proprietary, gitlab-hosted FreeSense-repoc
# (a binary that authenticated to Netgate and fetched per-device repo
# entitlements + client certs). FreeSense channels are public and
# fingerprint-signed, so the client is a small POSIX-sh script that
# materializes the channel list from a public manifest. No build-time network
# dependency (it only uses curl at RUNTIME, already part of the base system).
# poudriere_rename_ports turns this whole port into FreeSense-repoc at build.

NO_MTREE=	yes
NO_BUILD=	yes

PLIST_FILES=	sbin/FreeSense-repoc \
		sbin/FreeSense-repoc-static

.include <bsd.port.pre.mk>

do-extract:
	@${MKDIR} ${WRKSRC}
	${CP} -r ${FILESDIR}/* ${WRKSRC}

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/sbin
	${INSTALL_SCRIPT} ${WRKSRC}/FreeSense-repoc \
		${STAGEDIR}${PREFIX}/sbin/FreeSense-repoc
	${INSTALL_SCRIPT} ${WRKSRC}/FreeSense-repoc \
		${STAGEDIR}${PREFIX}/sbin/FreeSense-repoc-static

.include <bsd.port.post.mk>
