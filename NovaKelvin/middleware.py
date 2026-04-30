from django.http import HttpResponse


class UnderConstructionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]

        if host in ('kelvin-symphony.co.uk', 'www.kelvin-symphony.co.uk'):
            return HttpResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kelvin Symphony Orchestra</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        'kelvin': '#008888',
                        'kelvin-dark': '#006666',
                        'kelvin-light': '#00aaaa',
                    }
                }
            }
        }
    </script>
</head>
<body class="font-sans bg-gray-900 text-white min-h-screen flex flex-col">

    <!-- Hero -->
    <section class="relative flex-1 flex items-center justify-center min-h-screen overflow-hidden">
        <div class="absolute inset-0 bg-gradient-to-b from-black/60 via-black/50 to-black/60"></div>

        <div class="relative z-10 max-w-4xl mx-auto px-6 text-center">
            <div class="text-kelvin text-6xl mb-8">
                <i class="fas fa-music"></i>
            </div>
            <h1 class="text-5xl md:text-6xl lg:text-7xl font-bold mb-6 leading-tight">
                Kelvin Symphony Orchestra
            </h1>
            <div class="w-24 h-1 bg-kelvin mx-auto mb-8"></div>
            <p class="text-lg md:text-xl lg:text-2xl mb-4 text-gray-200 leading-relaxed max-w-3xl mx-auto">
                We're currently working on something exciting.
            </p>
            <p class="text-md md:text-lg text-gray-400 mb-12 max-w-2xl mx-auto">
                Our new website is under construction. Follow us on social media to stay up to date with our latest concerts and news. <br>For now, please continue to use our website at: <a href="https://www.kelvin-ensemble.co.uk/" class="text-kelvin">https://www.kelvin-ensemble.co.uk/</a>
            </p>

            <div class="flex flex-wrap justify-center gap-3">
                <a href="https://www.facebook.com/kelvinensemble/" class="w-10 h-10 rounded-full bg-gray-800 hover:bg-kelvin flex items-center justify-center text-kelvin-light hover:text-white transition-all">
                    <i class="fab fa-facebook-f"></i>
                </a>
                <a href="https://www.instagram.com/kelvinensemble/" class="w-10 h-10 rounded-full bg-gray-800 hover:bg-kelvin flex items-center justify-center text-kelvin-light hover:text-white transition-all">
                    <i class="fab fa-instagram"></i>
                </a>
            </div>
        </div>
    </section>

    
</body>
</html>
            """, status=200)

        return self.get_response(request)