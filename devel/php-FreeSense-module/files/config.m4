PHP_ARG_ENABLE([FreeSense],
  [whether to enable FreeSense support],
  [AS_HELP_STRING([--enable-FreeSense],
    [Enable FreeSense support])],
  [no])

PHP_ADD_INCLUDE(/usr/local/include)

PHP_ADD_LIBRARY_WITH_PATH(netgraph, /usr/lib, FREESENSE_SHARED_LIBADD)
PHP_ADD_LIBRARY_WITH_PATH(pfctl, /usr/lib, FREESENSE_SHARED_LIBADD)
PHP_ADD_LIBRARY_WITH_PATH(vici, /usr/local/lib/ipsec, FREESENSE_SHARED_LIBADD)

PHP_SUBST(FREESENSE_SHARED_LIBADD)

if test "$PHP_FREESENSE" != "no"; then
  AC_DEFINE(HAVE_FREESENSE, 1, [ Have FreeSense support ])
  PHP_NEW_EXTENSION(FreeSense, FreeSense.c %%DUMMYNET%% %%ETHERSWITCH%%, $ext_shared)
fi
