from dou_utils.log_utils import get_logger
from dou_utils.settings import SETTINGS

log = get_logger("teste.logger")
log.info("Linha de teste de log", extra={"etapa": "TESTE2"})
print("OK - import funcionou. Nivel =", SETTINGS.logging.level, "| log_file =", SETTINGS.logging.log_file)
