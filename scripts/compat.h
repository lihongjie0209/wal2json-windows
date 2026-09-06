/* Build-only compatibility for old Windows PostgreSQL development packages.
 * No server data structures are changed. Included before wal2json.c by /FI.
 */
#include "pg_config.h"

/* EDB's legacy archives can enable NLS but omit libintl.h/import libraries.
 * The plugin has no translation catalog: use the server headers' standard
 * non-NLS macros for plugin diagnostics only. Database text is unaffected.
 */
#undef ENABLE_NLS
#include "postgres.h"
#include "access/tupdesc.h"

/* Upstream later added these compatibility helpers; old wal2json tags lack
 * them. These are accessor/conversion macros, not replacement ABI layouts.
 */
#ifndef TupleDescAttr
#define TupleDescAttr(desc, i) ((desc)->attrs[(i)])
#endif
#ifndef UInt64GetDatum
#define UInt64GetDatum(value) Int64GetDatum((int64) (value))
#endif
