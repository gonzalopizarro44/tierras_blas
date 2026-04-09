# -*- coding: utf-8 -*-
import logging
import re
from odoo import http, _
from odoo.addons.auth_signup.controllers.main import AuthSignupHome
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

class CustomAuthSignupHome(AuthSignupHome):

    def _prepare_signup_values(self, qcontext):
        # Recogemos los valores habituales de Odoo (login, name, password)
        values = { key: qcontext.get(key) for key in ('login', 'name', 'password') }
        
        # En nuestro flujo personalizado (cuando no hay token/es signup directo), solo Nombre y Email son obligatorios
        if not qcontext.get('token'):
            if not values.get('login') or not values.get('name'):
                raise UserError(_("Los campos Nombre y Email son obligatorios."))
            
            # Validación de formato de email (mínimo un '@' y un '.')
            login = values.get('login')
            if login and (not "@" in login or not "." in login):
                raise UserError(_("El formato del email no es válido. Debe contener '@' y '.' (ej: usuario@ejemplo.com)"))
            
            # No validamos contraseñas porque están ocultas
            values.pop('password', None)
        else:
            # Si hay token (ej: reset password), seguimos el flujo normal de Odoo
            if values.get('password') != qcontext.get('confirm_password'):
                raise UserError(_("Passwords do not match; please retype them."))

        return values

    def _signup_with_values(self, token, values, do_login):
        # Registro nuevo (sin token) -> forzamos do_login=False para obligar activación por mail
        custom_flow = not token 
        
        login, password = request.env['res.users'].sudo().signup(values, token)
        
        if do_login and not custom_flow:
            credential = {'login': login, 'password': password, 'type': 'password'}
            request.session.authenticate(request.env, credential)
        
        # Si es nuestro flujo (signup directo), disparamos el mail de activación
        if custom_flow:
            user = request.env['res.users'].sudo().search([('login', '=', login)], limit=1)
            if user:
                user.with_context(create_user=1).action_reset_password()

    @http.route('/web/signup', type='http', auth='public', website=True, sitemap=False, captcha='signup')
    def web_auth_signup(self, *args, **kw):
        qcontext = self.get_auth_signup_qcontext()

        if request.httprequest.method == 'POST' and 'error' not in qcontext:
            try:
                self.do_signup(qcontext)
                
                # Si es un registro directo (sin token), mostramos mensaje de éxito con botón
                if not qcontext.get('token'):
                    qcontext['message'] = _("Revisá tu email %s para activar tu cuenta y crear tu contraseña.") % qcontext.get('login', '')
                    qcontext['signup_success'] = True
                    return request.render('auth_signup.signup', qcontext)
                
            except UserError as e:
                qcontext['error'] = e.args[0]
            except Exception as e:
                _logger.exception("Error en el registro")
                qcontext['error'] = str(e)

        return super(CustomAuthSignupHome, self).web_auth_signup(*args, **kw)
