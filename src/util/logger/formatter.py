# -*- coding: utf8 -*-

from __future__ import print_function
import logging
import re
import sys


__DEBUG__ = False

class Formatter(logging.Formatter):
    """
    Custom LogRecord formatter which handles string.format formatting and
    some custom keywords like '{color}'
    """

    ENCODING = sys.getfilesystemencoding()
    FORMAT = '%(asctime)s [%(levelname)s][%(process)s] %(message)s'
    FORMAT_NO_DATE = '[%(levelname)s][%(process)s] %(message)s'
    DATEFMT = '%m/%d@%H:%M:%S'

    ID_KEY = '__Formatter_ident__'

    # assumes 256 colors
    # EXCLUDE_COLORS = [0, 256] + range(16, 22) + range(232, 245)
    VALID_FG_COLORS = range(1, 15+1) + range(22, 231+1) + range(245, 256+1)
    __LEVEL_COLORS = {
            logging.DEBUG: (15, 8),
            logging.INFO: (15, None),
            logging.WARNING: (0, 202),
            logging.ERROR: (15, 1),
            logging.CRITICAL: (15, 201),
    }

    KEYWORD_REGEX_FMT = r'^\w*{0}\w*$'
    #             |\_/\_/\_/ \
    #             | |  |  | match entire string
    #             | |  | optionally match any trailing words
    #             | | match keyword (eg. 'color') optionally followed by
    #             |optionally match any leading words
    #            match entire string
    __REGEXES = {}

    __LARGE_TIME_UNITS = [
        ('d', 24*60*60),
        ('h', 60*60),
        ('m', 60),
        ('s', 1),
    ]
    __SMALL_TIME_UNITS =[
        ('ms', 1e-3),
        ('µs', 1e-6),
        ('ns', 1e-9),
        ('ps', 1e-12),
    ]
    __SIZE_UNITS = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']

    def __init__(self, fmt=FORMAT, datefmt=DATEFMT):
        logging.Formatter.__init__(self, fmt=fmt, datefmt=datefmt)

    def format(self, record):
        try:
            level_colors = Formatter.__LEVEL_COLORS[record.levelno]
        except KeyError:
            pass
        else:
            record.levelname = Formatter.color_msg(
                    # pad space to the end so that default level names align
                    '{0:<{1}}'.format(record.levelname, len('CRITICAL')),
                    level_colors[0],
                    level_colors[1],
            )

        try:
            if record.process:
                pid_fg = Formatter.color_fg(record.process)
                record.process = Formatter.color_msg(record.process, pid_fg)
        except AttributeError:
            pass

        def handle_special_keyword(
                keyword, format_func, *func_args, **func_kwargs
        ):
            regex = Formatter.__get_regex(keyword)
            # format all matching keywords in record.kwargs
            keys = [
                    m.group(0) for k in record.kwargs.keys()
                    for m in [regex.match(k)] if m
            ]
            for k in keys:
                record.kwargs[k] = format_func(
                        record.kwargs[k], *func_args, **func_kwargs
                )
            return keys

        # Note: most of these keywords are mutually exclusive (unpack is baked
        # into time, size, color). This mutual exclusion is not enforced, so
        # nothing will break if multiple special keywords are specified but the
        # behavior is probably not what you will want (whatever that may be).
        handle_special_keyword('unpack', Formatter.unpack)
        handle_special_keyword('pprint', Formatter.pprint)
        handle_special_keyword('time', Formatter.readable_time)
        handle_special_keyword('size', Formatter.readable_size)
        handle_special_keyword('yesno', Formatter.yesno)
        # XXX: handle color last because it alters the text
        handle_special_keyword('color', Formatter.get_fg_color_msg)

        msg = Formatter.__stringify(record.msg)
        try:
            record.msg = msg.format(*record.args, **record.kwargs)
        except (IndexError, KeyError, ValueError):
            # missing string.format arguments:
            # could be a typo or the msg could just contain '{}'
            # or mixing '{0} {}' formatting
            escaped_msg = Formatter.__handle_bad_msg(
                    msg, record.args, record.kwargs,
            )
            try:
                record.msg = escaped_msg.format(*record.args, **record.kwargs)

            except Exception as e:
                import traceback
                # failed to catch some edge-case in __handle_bad_msg
                # (could be missing format_spec info eg. '{0:{}}')
                print(
                        'Could not format \'{msg}\''
                        '\nargs:   {args}'
                        '\nkwargs: {kwargs}'.format(
                            msg=escaped_msg,
                            args=record.args,
                            kwargs=record.kwargs,
                        )
                )
                try:
                    trace = traceback.format_exc()
                except KeyError as key_err:
                    # failed get traceback ..
                    print(
                            'Failed to print traceback ({type}: {err})'.format(
                                type='.'.join([
                                    key_err.__module__,
                                    key_err.__class__.__name__,
                                ]),
                                err=key_err.message,
                            )
                    )
                else:
                    print(trace)

                return ''

        # log an empty line if user called without msg (eg. logger.debug())
        cached_fmt = None
        if record.msg == '':
            cached_fmt = self._fmt
            self._fmt = ''

        record.args = tuple() # TODO: pop only used arguments
        formatted_msg = logging.Formatter.format(self, record)

        # reset the format
        if cached_fmt:
            self._fmt = cached_fmt

        return formatted_msg

    @staticmethod
    def __get_regex(keyword, ptn=KEYWORD_REGEX_FMT):
        try:
            regex = Formatter.__REGEXES[keyword]
        except KeyError:
            if ptn == Formatter.KEYWORD_REGEX_FMT:
                ptn = ptn.format(keyword)
            regex = re.compile(ptn)
            Formatter.__REGEXES[keyword] = regex
        return regex

    @staticmethod
    def __handle_bad_msg(msg, args, kwargs):
        """
        Handles any missing args/keywords in the format message string
        """
        try:
            str_formatter = Formatter.__STR_FORMATTER
        except AttributeError:
            import string
            str_formatter = string.Formatter()
            Formatter.__STR_FORMATTER = str_formatter

        def do_replace(field='', spec=''):
            if spec and not spec.startswith(':'):
                spec = ':' + spec
            ptn = ''.join([
                '(\{',
                # escape in case '{}' appears in either
                # (eg. '>{1}' in regex means repeat '>' once)
                re.escape(str(field)),
                re.escape(str(spec)),
                '\})'
            ])
            if __DEBUG__:
                print('enclosing:', ptn, 'with {}')
            return re.sub(ptn, r'{\1}', msg)

        auto = []
        auto_children = []
        # map the order auto fields appear in case there are not enough args
        # (we cannot simply replace '{}' from the end in case of '{:{}}')
        auto_mapping = {}
        manual = []
        manual_children = []
        keyword_children = []
        def handle_field(field, format_spec='', parent=None):
            if field is not None:
                if not field:
                    # {}
                    data = None
                    if not parent:
                        auto.append( (field, format_spec) )
                        data = (auto, len(auto)-1)
                    else:
                        auto_children.append( (field, format_spec) )
                        data = (auto_children, len(auto_children)-1)
                    auto_mapping[len(auto_mapping)] = data

                elif field.isdigit():
                    # {69}
                    # store all manual fields in case an auto field exists
                    if not parent:
                        manual.append( (int(field), format_spec) )
                    else:
                        manual_children.append( (int(field), format_spec) )

                elif field not in kwargs:
                    # {foo}
                    if not parent:
                        # root-level field, just replace
                        return do_replace(field, format_spec)
                    else:
                        # probably a format_spec or otherwise not at root-level
                        # don't replace yet in case we need this field to format
                        # a root-level field later
                        keyword_children.append( (field, format_spec) )
            return msg

        # https://stackoverflow.com/a/37577590
        # https://hg.python.org/cpython/file/2.7/Lib/string.py#l634
        for text, field, format_spec, conversion in str_formatter.parse(msg):
            msg = handle_field(field, format_spec)

            # check if the format spec contains a format string
            # TODO: recursion required? I think it's theoretically possible
            # for an unbounded chain of format strings in format_specs but
            # why would someone do that ...?
            for _, spec_field, _, _ in str_formatter.parse(format_spec):
                msg = handle_field(spec_field, parent=field)

            if __DEBUG__:
                print('->', msg, end='\n\n')

        num_auto = len(auto_mapping)
        num_manual = len(manual) + len(manual_children)
        if num_auto > 0 and num_manual > 0:
            # cannot mix '{}' and '{0}'
            for field, spec in auto:
                msg = do_replace(field, spec)
            for field, spec in manual:
                msg = do_replace(field, spec)
            # replace children after so that root-level replacements behave
            # properly
            # -- the underlying issue is if do_replace is called on the "child"
            # elements first, then the "parent" elements will not substitute
            # properly since the child was changed
            for field, spec in auto_children:
                msg = do_replace(field, spec)
            for field, spec in manual_children:
                msg = do_replace(field, spec)

        else:
            if num_auto > 0:
                # too many '{}' fields

                # XXX: this is not perfect; it doesn't handle eg. '{:{}}' well
                for i in reversed(sorted(auto_mapping.keys())):
                    if len(args) <= i:
                        _list, idx = auto_mapping[i]
                        field, spec = _list[idx]
                        msg = do_replace(field, spec)

#                 def rreplace(old, new, num):
#                     """
#                     replace last `num` occurrences of `old` with `new` in message

#                     https://stackoverflow.com/a/2556252
#                     """
#                     split = msg.rsplit(old, num)
#                     return new.join(split)
#                 msg = rreplace(r'{}', '{{}}', len(auto) - len(args))

            elif num_manual > 0:
                for field, spec in manual:
                    if len(args) <= field:
                        msg = do_replace(field, spec)
                for field, spec in manual_children:
                    if len(args) <= field:
                        msg = do_replace(field, spec)

        # format any missing "child" fields eg. '{bar}' in '{foo:{bar}}'
        for field, spec in keyword_children:
            msg = do_replace(field, spec)

        return msg

    @staticmethod
    def __encode(msg, encoding=ENCODING):
        if isinstance(msg, unicode):
            return msg.encode(encoding, 'replace')
        return msg

    @staticmethod
    def __decode(msg, encoding=ENCODING):
        if isinstance(msg, str):
            return msg.decode(encoding, 'replace')
        return msg

    @staticmethod
    def __stringify(msg):
        if not isinstance(msg, basestring):
            msg = str(msg)
        else:
            msg = Formatter.__encode(msg)
        return msg

    @staticmethod
    def __choose_color(color_dict, msg, valid):
        """
        Chooses a persistent color for the given msg
        """
        import random
        msg = Formatter.__stringify(msg)
        try:
            msg_color = color_dict[msg]
        except KeyError:
            msg_color = random.choice(valid)
            color_dict[msg] = msg_color
        return msg_color

    @staticmethod
    def color_fg(msg, valid=VALID_FG_COLORS):
        """
        Chooses a color to use for the foreground
        """
        try:
            fg_colors = Formatter.__colors_foreground
        except AttributeError:
            fg_colors = {}
            Formatter.__colors_foreground = fg_colors
        return Formatter.__choose_color(fg_colors, msg, valid)

    @staticmethod
    def color_bg(msg, valid=range(0, 256+1)):
        """
        Chooses a color to use for the background
        """
        try:
            bg_colors = Formatter.__colors_background
        except AttributeError:
            bg_colors = {}
            Formatter.__colors_background = bg_colors
        return Formatter.__choose_color(bg_colors, msg, valid)

    @staticmethod
    def color_msg(msg, fg, bg=None):
        """
        Returns the color-formatted {msg} string
        """
        full_msg = ['\033[38;5;{0}'.format(fg)]
        if bg:
            full_msg.append(';48;5;{0}'.format(bg))
        full_msg.append('m{0}\033[m'.format(Formatter.__stringify(msg)))
        return ''.join(full_msg)

    @staticmethod
    def get_fg_color_msg(msg):
        """
        Chooses a foreground color for {msg} and returns the color-formatted
        string
        """
        def get_color(msg):
            return Formatter.color_msg(msg, Formatter.color_fg(msg))

        return Formatter.unpack(msg, get_color)

    @staticmethod
    def unpack(seq, func=lambda e: e, *func_args, **func_kwargs):
        """
        Unpacks the {seq}, applying {func} on each element. If {seq} is a dict,
        this will only unpack the keys.
        """
        if hasattr(seq, '__iter__'):
            return ', '.join([
                    func(element, *func_args, **func_kwargs)
                    for element in seq
            ])
        return func(seq, *func_args, **func_kwargs)

    @staticmethod
    def __readable_time(seconds):
        """
        Formats {seconds} into a human readable string
        """
        try:
            seconds = float(seconds)
        except (ValueError, TypeError):
            return seconds

        if seconds == 0:
            return '00s'

        is_negative = seconds < 0
        seconds = abs(seconds)

        time_parts = {}
        def split_time(seconds, UNITS):
            for unit, div in UNITS:
                time_parts[unit] = int(seconds / div)
                if time_parts[unit] > 0:
                    seconds -= (time_parts[unit] * div)

            # construct human readable string format, skipping parts that are 0
            # '{d}d{h}h{m}m{s}s'
            fmt = [filter(None, '{{{0}:02d}}{0}'.format(u)
                if time_parts[u] > 0 else '')
                for u, _ in UNITS
            ]
            if is_negative:
                fmt.insert(0, '-')
            return ''.join(fmt)

        fmt = split_time(seconds, Formatter.__LARGE_TIME_UNITS)
        if not fmt:
            fmt = split_time(seconds, Formatter.__SMALL_TIME_UNITS)

        return fmt.format(**time_parts)

    @staticmethod
    def readable_time(seconds):
        return Formatter.unpack(seconds, Formatter.__readable_time)

    @staticmethod
    def __readable_size(size, suffix='B'):
        """
        Formats {size} into a human readable string
        """
        try:
            size = float(size)
        except (ValueError, TypeError):
            return size

        prefix = 'Y'
        for unit in Formatter.__SIZE_UNITS:
            if abs(size) < float(2**10):
                prefix = unit
                break
            size /= float(2**10)
        return '{0:3.2f} {1}{2}'.format(size, prefix, suffix)

    @staticmethod
    def readable_size(size, suffix='B'):
        return Formatter.unpack(size, Formatter.__readable_size, suffix=suffix)

    @staticmethod
    def yesno(value):
        return 'yes' if bool(value) else 'no'

    @staticmethod
    def pprint(thing):
        import pprint
        return pprint.pformat(thing)


__all__ = [
        'Formatter',
]

