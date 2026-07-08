import requests


def get_weather():

    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=47.2529"
        "&longitude=-122.4443"
        "&current=temperature_2m,precipitation,rain"
    )

    response = requests.get(url, timeout=20)

    data = response.json()

    current = data["current"]

    return current


if __name__ == "__main__":

    weather = get_weather()

    print(weather)