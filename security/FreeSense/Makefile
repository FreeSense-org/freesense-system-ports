PORTNAME=	FreeSense
DISTVERSION=	${PRODUCT_VERSION}
DISTVERSIONPREFIX=	v
CATEGORIES=	security
MASTER_SITES=
DISTFILES=
EXTRACT_ONLY=

MAINTAINER=	dev@freesense.org
COMMENT?=	Main FreeSense package

LICENSE=	APACHE20

FREESENSE_PACKAGE_TRAIN?=	0.0
RUN_DEPENDS=	FreeSense-system>=0:security/FreeSense-system \
		FreeSense-platform-abi=${FREESENSE_PACKAGE_TRAIN}.0:sysutils/FreeSense-platform-abi

NO_BUILD=	yes
NO_MTREE=	yes

CONFLICTS=	FreeSense-vmware-[0-9]*

PLIST_FILES=	/etc/platform \
		/etc/version.buildtime \
		/etc/version.lastcommit \
		/etc/version.patch

do-install:
	${MKDIR} ${STAGEDIR}/etc
	${ECHO} "${PRODUCT_NAME}" > ${STAGEDIR}/etc/platform
	${ECHO} ${PORTREVISION} > ${STAGEDIR}/etc/version.patch
	${ECHO} "${FREESENSE_COMMITHASH}" > ${STAGEDIR}/etc/version.lastcommit
	${ECHO} "${FREESENSE_DATESTRING}" > ${STAGEDIR}/etc/version.buildtime

.include <bsd.port.mk>
