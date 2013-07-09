from __future__ import absolute_import

from time import strptime, mktime
from datetime import datetime
import fnmatch
import os

from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean,\
    Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from pyfits import getheader as get_pyfits_header

__all__ = [
    'FitsHeaderEntry', 'Tag', 'DatabaseEntry', 'entries_from_query_result',
    'entries_from_path']

Base = declarative_base()

# required for the many-to-many relation on tags:entries
association_table = Table('association', Base.metadata,
    Column('tag_id', Integer, ForeignKey('tags.id')),
    Column('entry_id', Integer, ForeignKey('data.id'))
)


# TODO: move this function outside this package (sunpy.util? sunpy.time?)
def timestamp2datetime(format, string):
    return datetime.fromtimestamp(mktime(strptime(string, format)))


class FitsHeaderEntry(Base):
    __tablename__ = 'fitsheaderentries'
    __hash__ = None

    id = Column(Integer, primary_key=True)
    dbentry_id = Column(Integer, ForeignKey('data.id'))
    key = Column(String, nullable=False)
    value = Column(String, nullable=False)

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __eq__(self, other):
        return (
            self.id == other.id and
            self.key == other.key and
            self.value == other.value)

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):  # pragma: no cover
        return '<%s(id %s, key %r, value %r)>' % (
            self.__class__.__name__, self.id, self.key, self.value)


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return self.id == other.id and self.name == other.name

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):  # pragma: no cover
        return '<%s(id %s, name %r)>' % (
            self.__class__.__name__, self.id, self.name)


class DatabaseEntry(Base):
    __tablename__ = 'data'
    __hash__ = None

    # FIXME: primary key is data provider + file ID + download_time!
    id = Column(Integer, primary_key=True)
    source = Column(String)
    provider = Column(String)
    physobs = Column(String)
    fileid = Column(String)
    observation_time_start = Column(DateTime)
    observation_time_end = Column(DateTime)
    instrument = Column(String)
    size = Column(Float)
    mission = Column(String)  # FIXME: does this info really exist?!
    waveunit = Column(String)
    wavemin = Column(Float)
    wavemax = Column(Float)
    path = Column(String)
    download_time = Column(DateTime)
    starred = Column(Boolean)
    fits_header_entries = relationship('FitsHeaderEntry', backref='data')
    tags = relationship('Tag', secondary=association_table, backref='data')

    @classmethod
    def from_query_result_block(cls, qr_block):
        """Make a new ``DatabaseEntry`` instance from a VSO query result block.
        A query result block is usually not created directly; instead, one gets
        instances of ``suds.sudsobject.QueryResponseBlock`` by iterating over
        a VSO query result.

        Examples
        --------
        >>> from sunpy.net import vso
        >>> from sunpy.database import DatabaseEntry
        >>> client = vso.VSOClient()
        >>> qr = client.query(vso.attrs.Time('2001/1/1', '2001/1/2'), vso.attrs.Instrument('eit'))
        >>> DatabaseEntry.from_query_result_block(qr[0])
        <DatabaseEntry(id None, data provider SDAC, fileid /archive/soho/private/data/processed/eit/lz/2001/01/efz20010101.010014)>

        """
        time_start = timestamp2datetime('%Y%m%d%H%M%S', qr_block.time.start)
        time_end = timestamp2datetime('%Y%m%d%H%M%S', qr_block.time.end)
        wave = qr_block.wave
        return cls(
            source=qr_block.source, provider=qr_block.provider,
            physobs=qr_block.physobs, fileid=qr_block.fileid,
            observation_time_start=time_start, observation_time_end=time_end,
            instrument=qr_block.instrument, size=qr_block.size,
            waveunit=wave.waveunit, wavemin=float(wave.wavemin),
            wavemax=float(wave.wavemax))

    @classmethod
    def from_fits_filepath(cls, path):
        """Make a new ``DatabaseEntry`` instance by using the method
        ``add_fits_header_entries_from_file``. This classmethod is simply a
        shortcut for the following lines::

            entry = DatabaseEntry()
            entry.add_fits_header_entries_from_file(path)

        See Also
        --------
        :method:`add_fits_header_entries_from_file`

        """
        entry = cls()
        entry.add_fits_header_entries_from_file(path)
        return entry

    def add_fits_header_entries_from_file(self, fits_filepath):
        """Use the header of a FITS file to add this information to this
        database entry. It will be saved in the attribute
        ``fits_header_entries``.

        Parameters
        ----------
        fits_filepath : file path or file-like object
            File to get header from.  If an opened file object, its mode
            must be one of the following rb, rb+, or ab+).

        Examples
        --------
        >>> from pprint import pprint
        >>> from sunpy.database import DatabaseEntry
        >>> import sunpy
        >>> entry = DatabaseEntry()
        >>> entry.fits_header_entries
        []
        >>> entry.add_fits_header_entries_from_file(sunpy.RHESSI_EVENT_LIST)
        >>> pprint(entry.fits_header_entries)
        [<FitsHeaderEntry(id None, key 'SIMPLE', value True)>,
         <FitsHeaderEntry(id None, key 'BITPIX', value 8)>,
         <FitsHeaderEntry(id None, key 'NAXIS', value 0)>,
         <FitsHeaderEntry(id None, key 'EXTEND', value True)>,
         <FitsHeaderEntry(id None, key 'DATE', value '2011-09-13T15:37:38')>,
         <FitsHeaderEntry(id None, key 'ORIGIN', value 'RHESSI')>,
         <FitsHeaderEntry(id None, key 'OBSERVER', value 'Unknown')>,
         <FitsHeaderEntry(id None, key 'TELESCOP', value 'RHESSI')>,
         <FitsHeaderEntry(id None, key 'INSTRUME', value 'RHESSI')>,
         <FitsHeaderEntry(id None, key 'OBJECT', value 'Sun')>,
         <FitsHeaderEntry(id None, key 'DATE_OBS', value '2002-02-20T11:06:00.000')>,
         <FitsHeaderEntry(id None, key 'DATE_END', value '2002-02-20T11:06:43.330')>,
         <FitsHeaderEntry(id None, key 'TIME_UNI', value 1)>,
         <FitsHeaderEntry(id None, key 'ENERGY_L', value 25.0)>,
         <FitsHeaderEntry(id None, key 'ENERGY_H', value 40.0)>,
         <FitsHeaderEntry(id None, key 'TIMESYS', value '1979-01-01T00:00:00')>,
         <FitsHeaderEntry(id None, key 'TIMEUNIT', value 'd')>]

        See Also
        --------
        pyfits.getheader is used to read the FITS header.

        """
        header = get_pyfits_header(fits_filepath)
        fits_header_entries = [
            FitsHeaderEntry(key, value) for key, value in header.iteritems()]
        self.fits_header_entries.extend(fits_header_entries)

    def __eq__(self, other):
        return (
            self.id == other.id and
            self.source == other.source and
            self.provider == other.provider and
            self.physobs == other.physobs and
            self.fileid == other.fileid and
            self.observation_time_start == other.observation_time_start and
            self.observation_time_end == other.observation_time_end and
            self.instrument == other.instrument and
            self.size == other.size and
            self.mission == other.mission and
            self.waveunit == other.waveunit and
            self.wavemin == other.wavemin and
            self.wavemax == other.wavemax and
            self.path == other.path and
            self.download_time == other.download_time and
            self.starred == other.starred and
            self.fits_header_entries == other.fits_header_entries and
            self.tags == other.tags)

    def __ne__(self, other):  # pragma: no cover
        return not (self == other)

    def __repr__(self):
        return '<%s(id %s, data provider %s, fileid %s)>' % (
            self.__class__.__name__, self.id, self.provider, self.fileid)


def entries_from_query_result(qr):
    """Use a query response returned from ``VSOClient.query`` or
    ``VSOClient.query_legacy`` to generate instances of ``DatabaseEntry``.
    Return an iterator over those instances.

    Examples
    --------
    >>> from sunpy.net import vso
    >>> from sunpy.database import Database, entries_from_query_result
    >>> client = vso.VSOClient()
    >>> qr = client.query(vso.attrs.Time('2001/1/1', '2001/1/2'), vso.attrs.Instrument('eit'))
    >>> entries = entries_from_query_result(qr)
    >>> entries.next()
    <DatabaseEntry(id None, data provider SDAC, fileid /archive/soho/private/data/processed/eit/lz/2001/01/efz20010101.010014)>

    See Also
    --------
    VSOClient.query and VSOClient.query_legacy for information on how to query
    a VSO server.

    """
    return (DatabaseEntry.from_query_result_block(block) for block in qr)


def entries_from_path(fitsdir, recursive=False, pattern='*.fits'):
    """Search the given directory recursively for *.fits file names and use the
    corresponding FITS headers to generate instances of DatabaseEntry. Return
    an iterator over those instances.

    Parameters
    ----------
    fitsdir : string
        The directory where to look for FITS files.

    recursive : bool
        If True, the given directory will be searched recursively. Otherwise,
        only the given directory and no subdirectories are searched.

    pattern : string
        The pattern defines how FITS files are detected. The default is to
        collect all files with the filename extension *.fits.

    """
    for dirpath, dirnames, filenames in os.walk(fitsdir):
        filename_paths = (os.path.join(dirpath, name) for name in filenames)
        for path in fnmatch.filter(filename_paths, pattern):
            yield DatabaseEntry.from_fits_filepath(path)
        if not recursive:
            break
