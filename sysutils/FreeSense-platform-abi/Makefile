PORTNAME=	FreeSense-platform-abi
FREESENSE_PACKAGE_TRAIN?=	0.0
PORTVERSION=	${FREESENSE_PACKAGE_TRAIN}.0
CATEGORIES=	sysutils
MASTER_SITES=	# empty
DISTFILES=	# empty
EXTRACT_ONLY=	# empty

MAINTAINER=	dev@freesense.org
COMMENT=	FreeSense optional-package compatibility marker
WWW=		https://freesense.org/

LICENSE=	APACHE20

NO_ARCH=	yes
NO_BUILD=	yes
NO_MTREE=	yes

PLIST_FILES=	share/FreeSense/package-abi

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/share/FreeSense
	${ECHO_CMD} "${FREESENSE_PACKAGE_TRAIN}" > ${STAGEDIR}${PREFIX}/share/FreeSense/package-abi

.include <bsd.port.mk>
