import requests
from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN, REQUEST_TIMEOUT


class HomeAssistantClient:
    def __init__(self):
        self.base_url = HOME_ASSISTANT_URL
        self.headers = {
            "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
            "Content-Type": "application/json",
        }
        self.timeout = REQUEST_TIMEOUT

    def get_state(self, entity_id: str):
        url = f"{self.base_url}/api/states/{entity_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            else:
                print("HA ERROR:", response.status_code, response.text)
                return None
        except Exception as e:
            print("REQUEST ERROR:", e)
            return None

    def turn_on(self, entity_id: str) -> bool:
        domain = entity_id.split(".")[0]
        url = f"{self.base_url}/api/services/{domain}/turn_on"

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json={"entity_id": entity_id},
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return True
            print("TURN ON ERROR:", response.status_code, response.text)
            return False
        except Exception as e:
            print("TURN ON REQUEST ERROR:", e)
            return False

    def turn_off(self, entity_id: str) -> bool:
        domain = entity_id.split(".")[0]
        url = f"{self.base_url}/api/services/{domain}/turn_off"

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json={"entity_id": entity_id},
                timeout=self.timeout,
            )
            if response.status_code == 200:
                return True
            print("TURN OFF ERROR:", response.status_code, response.text)
            return False
        except Exception as e:
            print("TURN OFF REQUEST ERROR:", e)
            return False
