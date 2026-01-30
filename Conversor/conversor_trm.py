"""
Conversor TRM - Cliente para el servicio web de la Superintendencia Financiera
SRP: Solo maneja la comunicacion con el servicio TRM
OCP: Extensible para nuevos tipos de conversion
DIP: Depende de abstracciones (interfaces HTTP)
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional, Dict
from .exceptions import TRMServiceError, TRMValidationError


class ConversorTRM:
    """
    Cliente para consumir el servicio web TRM de la Superfinanciera

    SRP: Responsabilidad unica - obtener tasas de cambio TRM
    """

    WSDL_URL = "https://www.superfinanciera.gov.co/SuperfinancieraWebServiceTRM/TCRMServicesWebService/TCRMServicesWebService"
    SOAP_NAMESPACE = "http://action.trm.services.generic.action.superfinanciera.nexura.sc.com.co/"

    def __init__(self, timeout: int = 30):
        """
        Inicializa el cliente TRM

        Args:
            timeout: Tiempo maximo de espera para las peticiones (segundos)
        """
        self.timeout = timeout
        self.session = self._configurar_session_robusta()
        self.session.headers.update({
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': ''
        })

    def _configurar_session_robusta(self) -> requests.Session:
        """
        Configura session HTTP con resiliencia y connection pooling (SRP)

        Implementa:
        - Reintentos automaticos con backoff exponencial
        - Connection pooling optimizado
        - Manejo de conexiones cerradas por el servidor
        - Keep-alive configurado

        Returns:
            Session HTTP configurada y optimizada
        """
        session = requests.Session()

        # Estrategia de reintentos con backoff exponencial
        retry_strategy = Retry(
            total=3,  # 3 intentos totales
            backoff_factor=1,  # Espera: 0s, 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],  # Codigos HTTP a reintentar
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]  # Todos los metodos
        )

        # HTTPAdapter con connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,  # Maximo 10 conexiones simultaneas
            pool_maxsize=10,  # Tamano del pool
            pool_block=False  # No bloquear si el pool esta lleno
        )

        # Montar adapter para HTTP y HTTPS
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Configurar keep-alive
        session.headers.update({
            'Connection': 'keep-alive',
            'Keep-Alive': 'timeout=30, max=100'
        })

        return session

    def _construir_soap_request(self, fecha: Optional[str] = None) -> str:
        """
        Construye el request SOAP para consultar la TRM

        Args:
            fecha: Fecha en formato YYYY-MM-DD (opcional)

        Returns:
            String con el XML del request SOAP
        """
        fecha_elemento = f"<tcrmQueryAssociatedDate>{fecha}</tcrmQueryAssociatedDate>" if fecha else ""

        soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:act="{self.SOAP_NAMESPACE}">
    <soapenv:Header/>
    <soapenv:Body>
        <act:queryTCRM>
            {fecha_elemento}
        </act:queryTCRM>
    </soapenv:Body>
</soapenv:Envelope>"""

        return soap_request

    def _validar_formato_fecha(self, fecha: str) -> bool:
        """
        Valida que la fecha tenga el formato correcto YYYY-MM-DD

        Args:
            fecha: String con la fecha a validar

        Returns:
            True si el formato es valido

        Raises:
            TRMValidationError: Si el formato es invalido
        """
        try:
            datetime.strptime(fecha, '%Y-%m-%d')
            return True
        except ValueError:
            raise TRMValidationError(
                f"Formato de fecha invalido: '{fecha}'. Debe ser YYYY-MM-DD"
            )

    def _extraer_trm_de_respuesta(self, xml_response: str) -> Dict:
        """
        Extrae la informacion de TRM de la respuesta XML

        Args:
            xml_response: String con la respuesta XML del servicio

        Returns:
            Diccionario con la informacion de la TRM

        Raises:
            TRMServiceError: Si no se puede parsear la respuesta
        """
        try:
            root = ET.fromstring(xml_response)

            # Buscar el elemento 'return' de manera flexible
            # Intentar varias estrategias de busqueda
            response_elem = None

            # Estrategia 1: Buscar con namespace completo
            for elem in root.iter():
                if elem.tag.endswith('return'):
                    response_elem = elem
                    break

            if response_elem is None:
                raise TRMServiceError("No se encontro el elemento 'return' en la respuesta")

            # Extraer valores
            resultado = {
                'id': self._extraer_texto(response_elem, 'id'),
                'unit': self._extraer_texto(response_elem, 'unit'),
                'validityFrom': self._extraer_texto(response_elem, 'validityFrom'),
                'validityTo': self._extraer_texto(response_elem, 'validityTo'),
                'value': self._extraer_texto(response_elem, 'value'),
                'success': self._extraer_texto(response_elem, 'success')
            }

            # Validar que la consulta fue exitosa
            if resultado['success'] != 'true':
                raise TRMServiceError("El servicio reporto un error en la consulta")

            # Convertir el valor a float
            try:
                resultado['value'] = float(resultado['value'])
            except (ValueError, TypeError):
                raise TRMServiceError(f"Valor de TRM invalido: {resultado['value']}")

            return resultado

        except ET.ParseError as e:
            raise TRMServiceError(f"Error al parsear la respuesta XML: {str(e)}")
        except Exception as e:
            if isinstance(e, TRMServiceError):
                raise
            raise TRMServiceError(f"Error inesperado al procesar la respuesta: {str(e)}")

    def _extraer_texto(self, elemento: ET.Element, tag: str) -> str:
        """
        Extrae el texto de un elemento XML

        Args:
            elemento: Elemento XML padre
            tag: Tag del elemento a buscar

        Returns:
            Texto del elemento o cadena vacia
        """
        child = elemento.find(tag)
        return child.text if child is not None and child.text else ""

    def obtener_trm(self, fecha: Optional[str] = None) -> Dict:
        """
        Obtiene la TRM para una fecha especifica o la actual

        Args:
            fecha: Fecha en formato YYYY-MM-DD (opcional).
                   Si no se especifica, retorna la TRM actual

        Returns:
            Diccionario con la informacion de la TRM:
            {
                'id': ID de la TRM,
                'unit': 'COP',
                'validityFrom': Fecha desde cuando aplica,
                'validityTo': Fecha hasta cuando aplica,
                'value': Valor de la TRM (float),
                'success': 'true'
            }

        Raises:
            TRMValidationError: Si el formato de fecha es invalido
            TRMServiceError: Si hay error en la comunicacion con el servicio
        """
        # Validar fecha si se proporciona
        if fecha:
            self._validar_formato_fecha(fecha)

        # Construir request SOAP
        soap_request = self._construir_soap_request(fecha)

        try:
            # Realizar peticion
            response = self.session.post(
                self.WSDL_URL,
                data=soap_request.encode('utf-8'),
                timeout=self.timeout,
                verify=True  # Verificar certificado SSL
            )

            # Verificar status code
            response.raise_for_status()

            # Extraer y retornar TRM
            return self._extraer_trm_de_respuesta(response.text)

        except requests.exceptions.Timeout:
            raise TRMServiceError(
                f"Timeout al conectar con el servicio TRM (>{self.timeout}s)"
            )
        except requests.exceptions.SSLError as e:
            raise TRMServiceError(
                f"Error de certificado SSL: {str(e)}"
            )
        except requests.exceptions.ConnectionError as e:
            raise TRMServiceError(
                f"Error de conexion con el servicio TRM: {str(e)}"
            )
        except requests.exceptions.HTTPError as e:
            raise TRMServiceError(
                f"Error HTTP {response.status_code}: {str(e)}"
            )
        except requests.exceptions.RequestException as e:
            raise TRMServiceError(
                f"Error en la peticion al servicio TRM: {str(e)}"
            )

    def obtener_trm_valor(self, fecha: Optional[str] = None) -> float:
        """
        Obtiene solo el valor de la TRM (metodo de conveniencia)

        Args:
            fecha: Fecha en formato YYYY-MM-DD (opcional)

        Returns:
            Valor de la TRM como float

        Raises:
            TRMValidationError: Si el formato de fecha es invalido
            TRMServiceError: Si hay error en la comunicacion con el servicio
        """
        resultado = self.obtener_trm(fecha)
        return resultado['value']

    def convertir_usd_a_cop(self, monto_usd: float, fecha: Optional[str] = None) -> float:
        """
        Convierte un monto en USD a COP usando la TRM

        Args:
            monto_usd: Monto en dolares estadounidenses
            fecha: Fecha de la TRM a usar (opcional)

        Returns:
            Monto convertido en pesos colombianos

        Raises:
            TRMValidationError: Si el formato de fecha es invalido o monto invalido
            TRMServiceError: Si hay error en la comunicacion con el servicio
        """
        if monto_usd < 0:
            raise TRMValidationError("El monto en USD debe ser mayor o igual a cero")

        trm_valor = self.obtener_trm_valor(fecha)
        return monto_usd * trm_valor

    def convertir_cop_a_usd(self, monto_cop: float, fecha: Optional[str] = None) -> float:
        """
        Convierte un monto en COP a USD usando la TRM

        Args:
            monto_cop: Monto en pesos colombianos
            fecha: Fecha de la TRM a usar (opcional)

        Returns:
            Monto convertido en dolares estadounidenses

        Raises:
            TRMValidationError: Si el formato de fecha es invalido o monto invalido
            TRMServiceError: Si hay error en la comunicacion con el servicio
        """
        if monto_cop < 0:
            raise TRMValidationError("El monto en COP debe ser mayor o igual a cero")

        trm_valor = self.obtener_trm_valor(fecha)
        return monto_cop / trm_valor

    def cerrar_sesion(self):
        """Cierra la sesion HTTP"""
        self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cerrar_sesion()
