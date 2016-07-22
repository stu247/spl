#!/usr/bin/python

""" Sonos Play List command. """

from __future__ import print_function

"""
    Copyright 2015-2016 Jim Stuhlmacher.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import argparse
import os, sys, random
import xml.etree.ElementTree as ET
import soco
try:
    import html
except ImportError:
    import cgi as html
import codecs
from pprint import pprint

class SPL:
    """ Main class."""

    def setPlayMode(self, speaker, playMode):
        """ Set the play mode and cross fade on the speaker. """
        if playMode.lower() != 'srf':
            print('Error: unknown playMode format: ' + playMode)
            mode = 'SHUFFLE'
        elif 'R' not in playMode and 'S' not in playMode:
            mode = 'NORMAL'
        elif 'R' in playMode and 'S' not in playMode:
            mode = 'REPEAT_ALL'
        elif 'R' in playMode and 'S' in playMode:
            mode = 'SHUFFLE'
        elif 'R' not in playMode and 'S' in playMode:
            mode = 'SHUFFLE_NOREPEAT'
        try:
            speaker.play_mode = mode
            if 'F' in playMode:
                speaker.cross_fade = True
            else:
                speaker.cross_fade = False
        except:
            print('Error: cannot communicate with the speaker.')

    def getPlayMode(self, speaker):
        """ Retrieve the play mode and cross fade from the speaker. """
        mode = speaker.play_mode
        if mode == 'NORMAL':
            pm = 'sr'
        elif mode == 'REPEAT_ALL':
            pm = 'sR'
        elif mode == 'SHUFFLE':
            pm = 'SR'
        elif mode == 'SHUFFLE_NOREPEAT':
            pm = 'Sr'
        else:
            print('Error: speaker gave an unknown play_mode: ' + mode)
            pm = 'xx'
        if speaker.cross_fade == True:
            return pm + 'F'
        return pm + 'f'


    def queue(self, speaker, pl, playMode):
        """ Replace queue on speaker with playlist. """
        try:
            speaker.clear_queue()
        except:
            # queue must be empty
            pass
        speaker.add_to_queue(pl)
        if 'S' in playMode:
            idx = random.randint(0, speaker.queue_size-1)
        else:
            idx = 0
        try:
            speaker.play_from_queue(idx)
        except:
            print("Error: could not play_from_queue")


    def exportPl(self, speaker, pl, force, details):
        """ Export playlist from speaker to an XSPF file. """
        fileName = pl.title.replace('/', '_').replace('\\', '_') + '.xspf'
        if not force and os.path.isfile(fileName):
            print('Error: file already exists: ' + fileName)
            return
        try:
            with codecs.open(fileName, 'w', 'utf-8') as fp:
                fp.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                fp.write('<playlist version="1" xmlns="http://xspf.org/ns/0/">\n')
                fp.write(' <title>%s</title>\n' % pl.title)
                fp.write(' <trackList>\n')
                start = 0
                max_items = 100
                cnt = 0
                while True:
                    trackList = speaker.browse(pl, start=start,
                                               max_items=max_items)
                    if not trackList:
                        break       # done
                    for item in trackList:
                        fp.write('  <track>\n')
                        if 'C' in details and hasattr(item, 'creator'):
                            creator = html.escape(item.creator, True)
                            fp.write('   <creator>%s</creator>\n' % creator)
                        if 'T' in details and hasattr(item, 'title'):
                            title = html.escape(item.title, True)
                            fp.write('   <title>%s</title>\n' % title)
                        if 'A' in details and hasattr(item, 'album'):
                            album = html.escape(item.album, True)
                            fp.write('   <album>%s</album>\n' % album)
                        if 'L' in details:
                            fp.write('   <location>%s</location>\n'
                                     % item.resources[0].uri)
                        fp.write('  </track>\n')
                        cnt += 1
                    start += max_items
                fp.write(' </trackList>\n')
                fp.write('</playlist>\n')
        except IOError as e:
            print("Error: file {0}: {1}".format(fileName, e.strerror))
            return
        print(pl.title + ': ' + str(cnt) + ' songs')


    def importPl(self, speaker, fileName):
        """ Import playlist from file to speaker. """
        try:
            with open(fileName, 'r') as fp:
                state = 'checkFile'
                firstTrack = True
                ns = '{http://xspf.org/ns/0/}'
                context = ET.iterparse(fp, events=('start', 'end'))

                for event, elem in context:
                    #print('State: %s Event: %s Tag: %s' % \
                    #      (state, event, elem.tag))
                    if state == 'checkFile':
                        if elem.tag == ns+'playlist':
                            state = 'findTitle'
                        else:
                            print('Error: file is not an xspf file: '+ fileName)
                            return
                    elif state == 'findTitle':
                        if elem.tag == ns+'title' and event == 'start':
                            #print(elem.text)
                            plName = elem.text
                            foundIt = False
                            for pl in speaker.get_sonos_playlists():
                                if pl.title == plName:
                                    foundIt = True
                            if foundIt:
                                print('Error: Sonos playlist "%s" already'
                                      ' exists.  The playlist must be deleted'
                                      ' before importing.' % plName)
                                return
                            state = 'findLocation'
                    elif state == 'findLocation':
                        if elem.tag == ns+'location' and event == 'end':
                            if firstTrack:
                                speaker.clear_queue()
                                firstTrack = False
                            # process the track
                            print('.', end='')
                            sys.stdout.flush()
                            speaker.add_uri_to_queue(elem.text)
                if not firstTrack:
                    print('')
            speaker.create_sonos_playlist_from_queue(plName)
            speaker.clear_queue()
        except ET.ParseError:
            print('Error: invalid XML format.')
            return
        except IOError as e:
            print("Error: file {0}: {1}".format(fileName, e.strerror))
            return
        except:
            print('Error: ' + sys.exc_info()[0])


    def __init__(self):
        """ Process the command line arguments. """

        parser = argparse.ArgumentParser(description='''
Utility for Sonos playlists including backup and restore.
The backup file is XSPF format and is stored in the current directory.  For
import, the name of the playlist is stored in the XSPF file, it is not the
name of the file.
''')
        parser.add_argument('-l', '--listPlaylist', action='store_true',
                            help='List the playlists.')
        parser.add_argument('-S', '--listSpeakerInfo', action='store_true',
                            help='List information about the speakers.')
        parser.add_argument('-x', '--exportPlaylist', action='append',
                            help='Export the playlist.', metavar='PLAYLIST')
        parser.add_argument('-X', '--exportAllPlaylists', action='store_true',
                            help='Export all playlists.')
        parser.add_argument('-d', '--exportDetails', default='ACLT',
                            help='List specifying what information is in the'
                            ' export file.  Possible values are ACLT.'
                            ' A = album, C = creator, L = location, T = title.'
                            ' Default is ACLT.',
                            metavar='DETAILS')
        parser.add_argument('-f', '--force', action='store_true',
                            help='Force overwrite of export files.')
        parser.add_argument('-i', '--importPlaylistFile', action='append',
                            help='Import the playlist file.', metavar='FILE')
        parser.add_argument('-s', '--speaker',
                            help='Speaker name or IP address.')
        parser.add_argument('-P', '--partyModeOn', action='store_true',
                            help='Use all speakers.  Must be used with -s to'
                            ' designate the group coordinator.')
        parser.add_argument('-p', '--partyModeOff', action='store_true',
                            help='Stop party mode.')
        parser.add_argument('-q', '--replaceQueue', metavar='PLAYLIST',
                            help='Replace queue with playlist.  Speakers must'
                            ' be in party mode or option -s is required.')
        parser.add_argument('-m', '--playMode', default='SRf',
                        help='Play mode: SRF, S = shuffle on, R = repeat on,'
                            ' F = cross fade on.  Lower case is off.  Default'
                            ' is SRf when using -q option.')
        parser.add_argument('-v', '--volume',
                            help='Volume (0-100). +/- to increase/decrease.')
        parser.add_argument('-t', '--togglePausePlay', action='store_true',
                            help='Toggle pause/play.')
        parser.add_argument('-I', '--interface',
                            help='Interface address for discover (generally'
                            ' not needed).')
        args = parser.parse_args()
        if args.playMode:
            playMode = args.playMode
        else:
            playMode = 'SRf'

        # what speaker are we working with?
        speaker = None
        if args.interface:
            try:
                zones = soco.discover(interface_addr=args.interface)
            except:
                print('Error: invalid interface address: ' + args.interface)
                exit(-2)
        else:
            zones = soco.discover()
        if not zones:
            print('Error: discover returned no speakers.')
            if args.interface:
                print(' Either the interface is down or you have no Sonos'
                      ' speakers on the network.')
            else:
                print(' Either the interface is down, you have no Sonos'
                      ' speakers on the network, or you may\n need to use -I'
                      ' option.')
            exit(-2)
        speakerSelection = ''
        try:
            if args.speaker:
                for zone in zones:
                    if zone.ip_address == args.speaker or \
                       zone.player_name == args.speaker:
                        speaker = zone
                        speakerSelection = 'specific'
                        break
            else:
                for zone in zones:
                    speaker = zone
                    speakerSelection = 'random'
                    break
        except:
            print('Error: could not discover any speakers.')
            exit(-2)
        if not speaker:
            print('Error: unable to find speaker.')
            exit(-1)
        if len(speaker.group.members) > 1:
            # we are in party mode, use the coordinator
            speakerSelection = 'party'
            speaker = speaker.group.coordinator

        # list the playlists
        if args.listPlaylist:
            for pl in speaker.get_sonos_playlists():
                print(pl.title)
            exit(0)

        # list info about the speakers
        if args.listSpeakerInfo:
            for zone in sorted(zones, key=lambda dev: dev.player_name):
                print(zone.player_name)
                print('  IP : ' + zone.ip_address)
                independent = True
                if speakerSelection == 'party':
                    print('  group coordinator : ' + \
                          zone.group.coordinator.player_name)
                    if zone != zone.group.coordinator:
                        independent = False
                if independent:
                    try:
                        tranInfo = zone.get_current_transport_info()
                        state = tranInfo[u'current_transport_state']
                        print('  state : ' + state)
                        print('  mode : ' + self.getPlayMode(zone))
                        print('  volume : ' + str(zone.volume))
                        info = zone.get_current_track_info()
                        artist = info[u'artist']
                        if artist and artist != '':
                            print('  artist : ' + artist)
                        title = info[u'title']
                        if title and title != '':
                            print('  title : ' + title)
                        #pprint(tranInfo)
                        #pprint(info)
                    except:
                        print('Error: cannot communicate with the speaker.')
            exit(0)

        if args.partyModeOff and args.partyModeOn:
            print('Error: can not have party mode on and off at the same time.')
            exit(-2)

        # music everywhere!
        if args.partyModeOn:
            if speakerSelection == 'party':
                print('Error: speakers are already in party mode.')
                exit(-2)
            if speakerSelection != 'specific':
                print('Error: speaker must be specified (-s) to turn on'
                      ' party mode.')
                exit(-2)
            try:
                speaker.partymode()
            except:
                print('Error: cannot communicate with one of the speaker.')
            exit(0)

        # party over :-(
        if args.partyModeOff:
            try:
                for device in speaker.group.members:
                    if not device == device.group.coordinator:
                        device.unjoin()
            except:
                print('Error: cannot communicate with one of the speaker.')
            exit(0)

        # toggle pause/play
        if args.togglePausePlay:
            if speakerSelection == 'random':
                print('Error: speaker must be specified (-s) or the speakers'
                      ' are already in party mode (-P) to toggle pause/play.')
                exit(-2)
            try:
                state = speaker.get_current_transport_info()\
                        [u'current_transport_state']
                if state == 'PLAYING':
                    speaker.pause()
                    print('Speaker now paused.')
                else:
                    speaker.play()
                    print('Speaker now playing.')
            except:
                print('Error: cannot communicate with the speaker.')
            exit(0)

        # export some or all the playlists
        if args.exportPlaylist or args.exportAllPlaylists:
            for pl in speaker.get_sonos_playlists():
                if args.exportAllPlaylists or pl.title in args.exportPlaylist:
                    self.exportPl(speaker, pl, args.force, args.exportDetails)
            exit(0)

        # import a playlist from a file
        if args.importPlaylistFile:
            for file in args.importPlaylistFile:
                self.importPl(speaker, file)
            exit(0)

        # set the volume
        if args.volume:
            if speakerSelection == 'random':
                print('Error: speaker must be specified (-s) or the speakers'
                      ' are already in party mode (-P) when setting volume.')
                exit(-2)
            try:
                vol = int(args.volume)
            except ValueError:
                print('Error: volume is not a number: ' + args.volume)
                exit(-2)
            if args.volume.startswith('+') or args.volume.startswith('-'):
                vol = speaker.volume + vol
            if vol < 0:
                print('Warning: volume too low, using 0')
                vol = 0
            elif vol > 100:
                print('Warning: volume too high, using 100')
                vol = 100
            try:
                if speakerSelection == 'party':
                    for member in speaker.group.members:
                        member.volume = vol
                else:
                    speaker.volume = vol
            except:
                print('Error: cannot communicate with the speaker.')

        # replace the queue with a playlist and start playing
        if args.replaceQueue:
            if speakerSelection == 'random':
                print('Error: speaker must be specified (-s) or the speakers'
                      ' are already in party mode (-P) when replacing queue.')
                exit(-2)
            foundIt = False
            for pl in speaker.get_sonos_playlists():
                if pl.title == args.replaceQueue:
                    foundIt = True
                    self.queue(speaker, pl, playMode)
            if not foundIt:
                print('Error: playlist for queue not found: ' + args.playlistQ)
                print(' Use -l option to see available playlists.')
                exit(-2)

        if args.playMode:
            if speakerSelection == 'random':
                print('Error: speaker must be specified (-s) or the speakers'
                      ' are already in party mode (-P) when changing playMode.')
                exit(-2)
            self.setPlayMode(speaker, playMode)

if __name__ == "__main__":
    spl = SPL()

