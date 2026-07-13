PHP_ARG_ENABLE([pfsense],
  [whether to enable pfsense support],
  [AS_HELP_STRING([--enable-pfsense],
    [Enable pfsense support])],
  [no])

PHP_ADD_INCLUDE(/usr/local/include)

PHP_ADD_LIBRARY_WITH_PATH(netgraph, /usr/lib, FREESENSE_SHARED_LIBADD)
PHP_ADD_LIBRARY_WITH_PATH(pfctl, /usr/lib, FREESENSE_SHARED_LIBADD)
PHP_ADD_LIBRARY_WITH_PATH(vici, /usr/local/lib/ipsec, FREESENSE_SHARED_LIBADD)

PHP_SUBST(FREESENSE_SHARED_LIBADD)

if test "$PHP_FREESENSE" != "no"; then
  AC_DEFINE(HAVE_PFSENSE, 1, [ Have pfsense support ])
  PHP_NEW_EXTENSION(FreeSense, FreeSense.c %%DUMMYNET%% %%ETHERSWITCH%%, $ext_shared)
fi
