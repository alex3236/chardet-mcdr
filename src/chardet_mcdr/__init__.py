import chardet
from mcdreforged.api.all import PluginServerInterface
from mcdreforged.mcdr_server import MCDReforgedServer
from mcdreforged.constants import core_constant
from subprocess import TimeoutExpired
from mcdreforged.utils.exception import DecodeError

original_func = None
original_decoding = None

def _decoding_test(buf: bytes, encoding):
    try:
        buf.decode(encoding)
        return True
    except UnicodeDecodeError:
        return False
    
def decoding_test(buf: bytes):
    TEST_LIST = ['utf8', 'gbk']
    detected = chardet.detect(buf)
    if detected['encoding'] and detected['confidence'] > 0.8:
        if _decoding_test(buf, detected['encoding']): 
            return detected['encoding']
    for encoding in TEST_LIST:
        if _decoding_test(buf, encoding):
            return encoding
    return None

def wrapped_func(*args, **kwargs):
        global original_decoding
        self = args[0]
        try:
            line_buf: bytes = next(iter(self.process.stdout))
        except StopIteration:  # server process has stopped
            for i in range(core_constant.WAIT_TIME_AFTER_SERVER_STDOUT_END_SEC):
                try:
                    self.process.wait(1)
                except TimeoutExpired:
                    self.logger.info(self.tr('mcdr_server.receive.wait_stop'))
                else:
                    break
            else:
                self.logger.warning('The server is still not stopped after {}s after its stdout was closed, killing'.format(core_constant.WAIT_TIME_AFTER_SERVER_STDOUT_END_SEC))
                self.__kill_server()
            self.process.wait()
            return None
        else:
            try:
                line_text: str = line_buf.decode(self.decoding_method)
            except Exception as e:
                try:
                    detected = decoding_test(line_buf)
                    if detected:
                        original_decoding = self.decoding_method
                        self.decoding_method = detected
                        line_text: str = line_buf.decode(self.decoding_method)
                    else:
                        raise e
                except Exception as err:
                    self.logger.error(self.tr('mcdr_server.receive.decode_fail', line_buf, err))
                    raise DecodeError()
            return line_text.strip('\n\r')

def on_load(psi: PluginServerInterface, prev):
    global original_func
    try:
        original_func = getattr(MCDReforgedServer, '_MCDReforgedServer__receive')
        setattr(MCDReforgedServer, '_MCDReforgedServer__receive', wrapped_func)
        psi.logger.info(f'§a成功修补 MCDReforgedServer: {MCDReforgedServer._MCDReforgedServer__receive}')
        psi.logger.warn('§e注意：此插件执行了未定义行为. 且不会在禁用时恢复. 在运行中如发现任何异常，先禁用此插件并重启 MCDR，再进行其他测试.')
    except Exception as e:
        psi.logger.error(f'§c未能修补 MCDReforgedServer: {e}')
