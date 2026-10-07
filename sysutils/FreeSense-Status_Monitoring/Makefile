PORTNAME=	FreeSense-Status_Monitoring
PORTVERSION=	1.8
PORTREVISION=	13
CATEGORIES=	sysutils
MASTER_SITES=	# empty
PKGNAMESUFFIX=	${PHP_PKGNAMESUFFIX}
DISTFILES=	# empty
EXTRACT_ONLY=	# empty

MAINTAINER=	dev@freesense.org
COMMENT=	FreeSense Status Monitoring

LICENSE=	APACHE20

RUN_DEPENDS+=	${PECL_PKGNAMEPREFIX}rrd>=2.0.0:databases/pecl-rrd@${PHP_FLAVOR}

# Only PHP 8.5 (DEFAULT_VERSIONS php=8.5) is supported. List every other
# version Mk/Uses/php.mk offers so no other flavor can be selected.
IGNORE_WITH_PHP=	82 83 84 86
USES=		php:flavors

NO_BUILD=	yes
NO_MTREE=	yes

PLIST_SUB=	PORTNAME=${PORTNAME}

do-extract:
	${MKDIR} ${WRKSRC}

do-install:
	${MKDIR} ${STAGEDIR}/etc/inc/priv
	${MKDIR} ${STAGEDIR}${PREFIX}/www
	${MKDIR} ${STAGEDIR}${PREFIX}/share/FreeSense/menu
	${INSTALL_DATA} ${FILESDIR}/etc/inc/priv/status_monitoring.priv.inc \
		${STAGEDIR}/etc/inc/priv/${PORTNAME}.priv.inc
	${INSTALL_DATA} ${FILESDIR}${PREFIX}/www/status_monitoring.php \
		${STAGEDIR}${PREFIX}/www
	${INSTALL_DATA} ${FILESDIR}${PREFIX}/www/rrd_fetch_json.php \
		${STAGEDIR}${PREFIX}/www
	${INSTALL_DATA} ${FILESDIR}${DATADIR}/menu.xml \
		${STAGEDIR}${PREFIX}/share/FreeSense/menu/${PORTNAME}.xml

.include <bsd.port.mk>
