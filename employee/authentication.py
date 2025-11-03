"""
Custom JWT Authentication for Employee model
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from .models import Employee


class EmployeeJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that uses Employee model instead of User model.
    This allows JWT tokens generated for Employee instances to be properly validated.
    """
    
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the validated token payload.
        Returns Employee instance instead of User instance.
        """
        try:
            # Get user_id from token payload
            user_id = validated_token.get('user_id')
            
            if user_id is None:
                raise InvalidToken('Token contained no recognizable user identification')
            
            # Try to get Employee with this ID
            try:
                employee = Employee.objects.get(id=user_id, is_active=True)
                return employee
            except Employee.DoesNotExist:
                raise InvalidToken('User not found')
                
        except KeyError:
            raise InvalidToken('Token contained no recognizable user identification')

