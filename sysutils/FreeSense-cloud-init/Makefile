PORTNAME=	FreeSense-cloud-init
PORTVERSION=	1.0.0
PORTREVISION=	5
CATEGORIES=	sysutils
MASTER_SITES=	# empty
DISTFILES=	# empty
EXTRACT_ONLY=	# empty

MAINTAINER=	dev@freesense.org
COMMENT=	Cloud-init adapter for native FreeSense configuration

LICENSE=	APACHE20

RUN_DEPENDS=	cloud-init:net/cloud-init

USES=		python:3.11+
SUB_FILES=	freesense-cloud-init
SUB_LIST=	PYTHON_CMD=${PYTHON_CMD}
NO_ARCH=	yes
NO_BUILD=	yes
NO_MTREE=	yes

PLIST_FILES=	sbin/freesense-cloud-init \
		etc/cloud/cloud.cfg.d/99-freesense.cfg \
		share/freesense/cloud-init/freesense_cloud_init.py

do-extract:
	@${MKDIR} ${WRKSRC}
	${CP} -r ${FILESDIR}/* ${WRKSRC}

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/sbin \
		${STAGEDIR}${PREFIX}/etc/cloud/cloud.cfg.d \
		${STAGEDIR}${PREFIX}/share/freesense/cloud-init
	${INSTALL_SCRIPT} ${WRKDIR}/freesense-cloud-init \
		${STAGEDIR}${PREFIX}/sbin/freesense-cloud-init
	${INSTALL_DATA} ${WRKSRC}/freesense_cloud_init.py \
		${STAGEDIR}${PREFIX}/share/freesense/cloud-init/freesense_cloud_init.py
	${INSTALL_DATA} ${WRKSRC}/99-freesense.cfg \
		${STAGEDIR}${PREFIX}/etc/cloud/cloud.cfg.d/99-freesense.cfg

.include <bsd.port.mk>
