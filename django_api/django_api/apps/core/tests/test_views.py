from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from account.models import User

from core.factories import LocationFactory, InterventionFactory
from core.models import Location, Intervention


class TestInterventionListAPIView(APITestCase):

    def setUp(self):
        self.locations = LocationFactory.create_batch(5)

        self.interventions = InterventionFactory.create_batch(5, locations=self.locations)
        self.count = Intervention.objects.count()

        # Make all requests in the context of a logged in session.
        admin, created = User.objects.get_or_create(username='admin', defaults={
            'email': 'admin@unicef.org',
            'is_superuser': True,
            'is_staff': True
        })
        admin.set_password('Passw0rd!')
        admin.save()
        self.client = APIClient()
        self.client.login(username='admin', password='Passw0rd!')

    def test_list_api(self):
        url = reverse('simple-intervention')
        response = self.client.get(url, format='json')

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(len(response.data), self.count)


class TestLocationListAPIView(APITestCase):

    def setUp(self):
        self.locations = LocationFactory.create_batch(5)
        self.count = Location.objects.count()

    def test_list_api(self):
        url = reverse('simple-location')
        response = self.client.get(url, format='json')

        self.assertEquals(response.status_code, status.HTTP_200_OK)
        self.assertEquals(len(response.data), self.count)
