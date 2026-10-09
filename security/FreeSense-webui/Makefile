PORTNAME=	FreeSense-webui
DISTVERSION=	2.0.0-alpha.0
PORTREVISION=	0
CATEGORIES=	security www

MAINTAINER=	dev@freesense.org
COMMENT=	FreeSense WebUI 2.0 (preview, served under /next/ next to the WebUI)
WWW=		https://github.com/FreeSense-org/freesense-webui

LICENSE=	APACHE20
LICENSE_FILE=	${WRKSRC}/LICENSE

RUN_DEPENDS=	FreeSense-system>=0:security/FreeSense-system

# The freesense-webui commit this package installs. Update it with
# `npm run port -- --ports <this checkout>` in freesense-webui, which also
# writes distinfo and pkg-plist (tools/webui_port_audit.py checks all three).
USE_GITHUB=	yes
GH_ACCOUNT=	FreeSense-org
GH_PROJECT=	freesense-webui
GH_TAGNAME=	3cdfa60e21492f69c5788c092cb144de9dc6983e

# dist/ (the built engine and themes) is committed in freesense-webui, so
# nothing is built here: no Node.js, no network beyond the pinned archive.
NO_ARCH=	yes
NO_BUILD=	yes

SUB_FILES=	pkg-install pkg-deinstall
SUB_LIST=	WEBROOT=${PREFIX}/www-ui
PKGINSTALL=	${WRKDIR}/pkg-install
PKGDEINSTALL=	${WRKDIR}/pkg-deinstall

DATADIR=	${PREFIX}/share/freesense-webui
WEBROOT=	${PREFIX}/www-ui

do-install:
	${MKDIR} ${STAGEDIR}${WEBROOT} ${STAGEDIR}${DATADIR}/app
	${INSTALL_DATA} ${WRKSRC}/app/public/index.php ${STAGEDIR}${WEBROOT}/index.php
	(cd ${WRKSRC}/dist/public && ${COPYTREE_SHARE} "ui themes" ${STAGEDIR}${WEBROOT})
	(cd ${WRKSRC}/app && ${COPYTREE_SHARE} "bootstrap.php nav.json pages.php src pages templates" ${STAGEDIR}${DATADIR}/app)
	${INSTALL_DATA} ${WRKSRC}/LICENSE ${WRKSRC}/NOTICE ${STAGEDIR}${DATADIR}

.include <bsd.port.mk>
