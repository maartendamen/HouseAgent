"""
The following was taken from the rrd_format.h file in the rrdtool source code.

The RRD Database Structure
---------------------------

In oder to properly describe the database structure lets define a few
new words:

 ds - Data Source (ds) providing input to the database. A Data Source (ds)
       can be a traffic counter, a temperature, the number of users logged
       into a system. The rrd database format can handle the input of
       several Data Sources (ds) in a singe database.

 dst - Data Source Type (dst). The Data Source Type (dst) defines the rules
       applied to Build Primary Data Points from the input provided by the
       data sources (ds).

 pdp - Primary Data Point (pdp). After the database has accepted the
       input from the data sources (ds). It starts building Primary
       Data Points (pdp) from the data. Primary Data Points (pdp)
       are evenly spaced along the time axis (pdp_step). The values
       of the Primary Data Points are calculated from the values of
       the data source (ds) and the exact time these values were
       provided by the data source (ds).

 pdp_st - PDP Start (pdp_st). The moments (pdp_st) in time where
       these steps occur are defined by the moments where the
       number of seconds since 1970-jan-1 modulo pdp_step equals
       zero (pdp_st).

 cf -  Consolidation Function (cf). An arbitrary Consolidation Function (cf)
       (averaging, min, max) is applied to the primary data points (pdp) to
       calculate the consolidated data point.

 cdp - Consolidated Data Point (cdp) is the long term storage format for data
       in the rrd database. Consolidated Data Points represent one or
       several primary data points collected along the time axis. The
       Consolidated Data Points (cdp) are stored in Round Robin Archives
       (rra).

 rra - Round Robin Archive (rra). This is the place where the
       consolidated data points (cdp) get stored. The data is
       organized in rows (row) and columns (col). The Round Robin
       Archive got its name from the method data is stored in
       there. An RRD database can contain several Round Robin
       Archives. Each Round Robin Archive can have a different row
       spacing along the time axis (pdp_cnt) and a different
       consolidation function (cf) used to build its consolidated
       data points (cdp).

 rra_st - RRA Start (rra_st). The moments (rra_st) in time where
       Consolidated Data Points (cdp) are added to an rra are
       defined by the moments where the number of seconds since
       1970-jan-1 modulo pdp_cnt*pdp_step equals zero (rra_st).

 row - Row (row). A row represent all consolidated data points (cdp)
       in a round robin archive who are of the same age.

 col - Column (col). A column (col) represent all consolidated
       data points (cdp) in a round robin archive (rra) who
       originated from the same data source (ds).

"""
RRD_COOKIE = "RRD"
VERSION2 = "0002"
VERSION3 = "0003"
VERSION4 = "0004"
FLOAT_COOKIE = 8.642135e130

# It looks like some of the header delimited with "\x00"
#   - splitting on that gives the RRD_COOKIE at index 0
#   - an the VERSION at index 1
