"""Login/Registration UI - email verification code + multi-step state machine

State flow:
  MODE_LOGIN       -> username/email + password -> login
   ├─"Register"    -> MODE_REGISTER_EMAIL -> email -> send code
   │                 └-> MODE_REGISTER_CODE  -> code + username + password -> register
   └─"Forgot?"     -> MODE_RESET_EMAIL    -> email -> send code
                     └-> MODE_RESET_CODE      -> code + new password -> reset
"""

import pygame


def _get_font(size, bold=False):
    """Get CJK-capable font, prefer Microsoft YaHei"""
    for name in ('Microsoft YaHei', 'SimHei', 'SimSun', 'Arial'):
        try:
            return pygame.font.SysFont(name, size, bold=bold)
        except Exception:
            continue
    return pygame.font.SysFont(None, size)


# State constants
(MODE_LOGIN, MODE_REGISTER_EMAIL, MODE_REGISTER_CODE,
 MODE_RESET_EMAIL, MODE_RESET_CODE) = range(5)


class LoginOverlay:
    """Login/Registration overlay"""

    def __init__(self, screen, web_client, player_data):
        self.screen = screen
        self.screen_rect = screen.get_rect()
        self.client = web_client
        self.player_data = player_data
        self.done = False
        self.token = ''
        self.username = ''
        self.email = ''

        # Enable text input (IME, @ symbol, etc.)
        pygame.key.start_text_input()

        # Auto login (if token exists)
        saved_token = self.player_data.get_token()
        saved_username = self.player_data.get_username()
        if saved_token and saved_username:
            self.token = saved_token
            self.username = saved_username
            self.email = self.player_data.get_email()
            self.done = True
            return

        # State machine
        self._mode = MODE_LOGIN
        self._active_field = 0
        self._status = ''
        self._status_color = (180, 180, 180)
        self._cursor_timer = 0
        self._countdown = 0  # Countdown after sending code
        self._countdown_max = 60

        # Input text per mode
        self._fields = ['', '', '', '']  # Index meanings per mode _field_labels

        # Font (CJK compatible)
        self._font_large = _get_font(42)
        self._font = _get_font(32)
        self._font_small = _get_font(24)
        self._font_hint = _get_font(20)

        # Colors
        self._bg = (25, 30, 50)
        self._inp_bg = (40, 45, 70)
        self._inp_active = (50, 55, 90)
        self._white = (255, 255, 255)
        self._gray = (160, 160, 180)
        self._green = (100, 220, 100)
        self._red = (220, 80, 80)
        self._blue = (80, 150, 240)
        self._gold = (255, 215, 0)

        # Click areas (dynamically calculated)
        self._click_rects = []

    # ------------------------------------------------------------------
    # Field config for current mode
    # ------------------------------------------------------------------
    @property
    def _field_labels(self):
        if self._mode == MODE_LOGIN:
            return ['Username / Email', 'Password']
        elif self._mode == MODE_REGISTER_EMAIL:
            return ['Email']
        elif self._mode == MODE_REGISTER_CODE:
            return ['Verification Code', 'Username', 'Password']
        elif self._mode == MODE_RESET_EMAIL:
            return ['Registered Email']
        elif self._mode == MODE_RESET_CODE:
            return ['Verification Code', 'New Password']
        return []

    @property
    def _field_masks(self):
        """Which fields are passwords (show *)"""
        if self._mode == MODE_LOGIN:
            return [False, True]
        elif self._mode == MODE_REGISTER_CODE:
            return [False, False, True]
        elif self._mode == MODE_RESET_CODE:
            return [False, True]
        return [False] * len(self._field_labels)

    @property
    def _field_max_len(self):
        labels = self._field_labels
        result = [32] * len(labels)
        for i, l in enumerate(labels):
            if 'Code' in l:
                result[i] = 6
        return result

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def handle_event(self, event):
        if self.done:
            return False
        if event.type == pygame.KEYDOWN:
            return self._handle_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            return self._handle_click(event.pos)
        return False

    # US keyboard Shift map (fixes unicode issue from stop_text_input)
    _US_SHIFT_MAP = {
        '`': '~', '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
        '6': '^', '7': '&', '8': '*', '9': '(', '0': ')',
        '-': '_', '=': '+', '[': '{', ']': '}', '\\': '|',
        ';': ':', "'": '"', ',': '<', '.': '>', '/': '?',
    }

    def _handle_key(self, event):
        labels = self._field_labels
        n_fields = len(labels)

        # Ctrl+V paste
        ctrl = event.mod & pygame.KMOD_CTRL
        if ctrl and event.key == pygame.K_v:
            if self._active_field < n_fields:
                try:
                    import subprocess
                    clip = subprocess.check_output(
                        ['powershell', '-command', 'Get-Clipboard'],
                        text=True, stderr=subprocess.DEVNULL).rstrip('\r\n')
                    if clip:
                        self._fields[self._active_field] += clip[:100]
                except Exception:
                    pass
            return True

        if event.key == pygame.K_TAB:
            self._active_field = (self._active_field + 1) % (n_fields + 1)
            self._cursor_timer = 0
            return True

        if event.key == pygame.K_RETURN:
            self._submit()
            return True

        if event.key == pygame.K_ESCAPE:
            if self._mode != MODE_LOGIN:
                self._mode = MODE_LOGIN
                self._active_field = 0
                self._status = ''
                self._fields = ['', '', '', '']
                self._countdown = 0
                return True
            return False

        if self._active_field >= n_fields:
            return False

        idx = self._active_field
        label = labels[idx]
        is_code = 'Code' in label
        is_email = 'Email' in label
        max_len = self._field_max_len[idx]

        if event.key == pygame.K_BACKSPACE:
            self._fields[idx] = self._fields[idx][:-1]
            self._cursor_timer = 0
            return True

        if not event.unicode or not event.unicode.isprintable():
            return False

        ch = event.unicode
        shift = event.mod & pygame.KMOD_SHIFT

        # Shift fix: stop_text_input causes unicode to not reflect Shift state
        if shift and len(ch) == 1 and ch in self._US_SHIFT_MAP:
            ch = self._US_SHIFT_MAP[ch]

        # Character filter
        if is_email:
            pass
        elif is_code:
            if not ch.isdigit():
                return True
        elif ch == ' ':
            return True

        current = self._fields[idx]
        if len(current) < max_len:
            self._fields[idx] += ch
        self._cursor_timer = 0
        return True

    def _handle_click(self, pos):
        if not self._click_rects:
            return False

        rects = self._click_rects

        # Check input fields
        for i in range(len(rects) - 3):
            if rects[i][0].collidepoint(pos):
                self._active_field = i
                self._cursor_timer = 0
                return True

        # Check primary button
        if len(rects) >= 3:
            main_btn = rects[-3][0]
            if main_btn.collidepoint(pos):
                self._submit()
                return True

        # Check secondary button
        if len(rects) >= 2:
            aux_btn = rects[-2][0]
            if aux_btn.collidepoint(pos):
                self._aux_action()
                return True

        # Check forgot password / tertiary button
        if len(rects) >= 1:
            third_btn = rects[-1][0]
            if third_btn.collidepoint(pos):
                self._forgot_action()
                return True

        return False

    def _forgot_action(self):
        """Forgot password -> reset mode"""
        if self._mode == MODE_LOGIN:
            self._mode = MODE_RESET_EMAIL
            self._active_field = 0
            self._fields = ['', '', '', '']
            self._status = ''
            self._countdown = 0

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------
    def _submit(self):
        if self._mode == MODE_LOGIN:
            id_ = self._fields[0].strip()
            pw = self._fields[1]
            if not id_ or not pw:
                self._set_status('Please enter username/email and password', self._red)
                return
            try:
                result = self.client.login(id_, pw)
            except Exception:
                result = {'error': 'Could not connect to server'}

        elif self._mode == MODE_REGISTER_EMAIL:
            email = self._fields[0].strip()
            if not email or '@' not in email:
                self._set_status('Please enter a valid email', self._red)
                return
            if self._countdown > 0:
                self._set_status(f'Please wait {self._countdown}s', self._gray)
                return
            try:
                result = self.client.send_code(email, 'register')
            except Exception:
                result = {'error': 'Could not connect to server'}

            if 'success' in result:
                self._register_email = email
                self._mode = MODE_REGISTER_CODE
                self._active_field = 0
                self._fields = ['', '', '', '']
                self._status = 'Verification code sent'
                self._status_color = self._green
                self._countdown = self._countdown_max
            return

        elif self._mode == MODE_REGISTER_CODE:
            email = self._fields[0] if len(self._fields) > 0 else ''
            code = self._fields[0].strip()
            username = self._fields[1].strip() if len(self._fields) > 1 else ''
            pw = self._fields[2] if len(self._fields) > 2 else ''
            if not code or len(code) != 6:
                self._set_status('Please enter 6-digit code', self._red)
                return
            if not username:
                self._set_status('Please set a username', self._red)
                return
            if len(username) < 2:
                self._set_status('Username must be at least 2 characters', self._red)
                return
            if not pw or len(pw) < 4:
                self._set_status('Password must be at least 4 characters', self._red)
                return
            try:
                result = self.client.register(
                    self._register_email, code, username, pw)
            except Exception:
                result = {'error': 'Could not connect to server'}

        elif self._mode == MODE_RESET_EMAIL:
            email = self._fields[0].strip()
            if not email or '@' not in email:
                self._set_status('Please enter a registered email', self._red)
                return
            if self._countdown > 0:
                self._set_status(f'Please wait {self._countdown}s', self._gray)
                return
            try:
                result = self.client.send_code(email, 'reset')
            except Exception:
                result = {'error': 'Could not connect to server'}

            if 'success' in result:
                self._register_email = email
                self._mode = MODE_RESET_CODE
                self._active_field = 0
                self._fields = ['', '', '', '']
                self._status = 'Verification code sent'
                self._status_color = self._green
                self._countdown = self._countdown_max
            return

        elif self._mode == MODE_RESET_CODE:
            code = self._fields[0].strip()
            new_pw = self._fields[1] if len(self._fields) > 1 else ''
            if not code or len(code) != 6:
                self._set_status('Please enter 6-digit code', self._red)
                return
            if not new_pw or len(new_pw) < 4:
                self._set_status('New password must be at least 4 characters', self._red)
                return
            try:
                result = self.client.reset_password(
                    self._register_email, code, new_pw)
            except Exception:
                result = {'error': 'Could not connect to server'}

            if result.get('success'):
                self._set_status('Password reset, please return to login', self._green)
                self._mode = MODE_LOGIN
                self._active_field = 0
                self._fields = ['', '', '', '']
                self._countdown = 0
            return

        if 'error' in result:
            self._set_status(result['error'], self._red)
        else:
            self.token = result['token']
            self.username = result.get('username', '')
            self.email = result.get('email', '')
            self.player_data.save_auth(self.token, self.username)
            if self.email:
                self.player_data.save_email(self.email)
            self._status = 'Login successful!'
            self._status_color = self._green
            self.done = True

    def _aux_action(self):
        """Secondary button: switch register/login/forgot"""
        if self._mode == MODE_LOGIN:
            self._mode = MODE_REGISTER_EMAIL
            self._active_field = 0
            self._fields = ['', '', '', '']
            self._status = ''
            self._register_email = ''
            self._countdown = 0
        elif self._mode == MODE_REGISTER_EMAIL:
            # "Back to login"
            self._mode = MODE_LOGIN
            self._fields = ['', '', '', '']
            self._status = ''
            self._countdown = 0
        elif self._mode == MODE_REGISTER_CODE:
            # "Resend verification code"
            if self._countdown > 0:
                return
            try:
                result = self.client.send_code(self._register_email, 'register')
            except Exception:
                result = {'error': 'Could not connect to server'}
            if 'success' in result:
                self._countdown = self._countdown_max
                self._set_status('Code resent', self._green)
            else:
                self._set_status(result.get('error', 'Send failed'), self._red)
        elif self._mode == MODE_RESET_EMAIL:
            # "Back to login"
            self._mode = MODE_LOGIN
            self._fields = ['', '', '', '']
            self._status = ''
            self._countdown = 0
        elif self._mode == MODE_RESET_CODE:
            # "Resend verification code"
            if self._countdown > 0:
                return
            try:
                result = self.client.send_code(self._register_email, 'reset')
            except Exception:
                result = {'error': 'Could not connect to server'}
            if 'success' in result:
                self._countdown = self._countdown_max
                self._set_status('Code resent', self._green)
            else:
                self._set_status(result.get('error', 'Send failed'), self._red)

    def _set_status(self, msg, color):
        self._status = msg
        self._status_color = color

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------
    def update(self):
        if self.done:
            return
        self._cursor_timer = (self._cursor_timer + 1) % 60
        if self._countdown > 0:
            self._countdown -= 1

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------
    def draw(self):
        if self.done:
            return

        # Semi-transparent overlay
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        self.screen.blit(overlay, (0, 0))

        labels = self._field_labels
        n_fields = len(labels)

        panel_w, panel_h = 580, n_fields * 72 + 300
        panel = pygame.Surface((panel_w, panel_h))
        panel.fill(self._bg)
        panel_rect = panel.get_rect(center=self.screen_rect.center)
        self.screen.blit(panel, panel_rect)
        px, py = panel_rect.topleft
        cx = px + panel_w // 2

        self._click_rects = []

        # Title
        title_map = {
            MODE_LOGIN: 'LOGIN', MODE_REGISTER_EMAIL: 'REGISTER',
            MODE_REGISTER_CODE: 'REGISTER', MODE_RESET_EMAIL: 'RESET PASSWORD',
            MODE_RESET_CODE: 'RESET PASSWORD',
        }
        title = self._font_large.render(title_map[self._mode], True, self._gold)
        self.screen.blit(title, (cx - title.get_width() // 2, py + 20))

        # Email hint (shown in register/reset mode)
        if self._mode in (MODE_REGISTER_CODE, MODE_RESET_CODE) and hasattr(self, '_register_email'):
            email_hint = self._font_small.render(
                self._register_email, True, self._gray)
            self.screen.blit(email_hint, (cx - email_hint.get_width() // 2, py + 60))
            field_start_y = py + 90
        else:
            field_start_y = py + 72

        # Input fields (labels right-aligned, input fields next)
        label_right = px + 155
        input_left = px + 170
        input_width = 375

        for i, label in enumerate(labels):
            row_y = field_start_y + i * 72
            self._draw_label_right(label_right, row_y, label)

            masked = self._field_masks[i]
            text = self._fields[i]
            display = '*' * len(text) if masked else text

            inp_rect = self._draw_input(
                input_left, row_y, display, input_width,
                active=(self._active_field == i))
            self._click_rects.append((inp_rect, None))

        # Countdown / Status
        status_y = field_start_y + n_fields * 72 + 5
        if self._countdown > 0:
            cd = self._font_small.render(
                f'Resend in {self._countdown}s', True, self._gray)
            self.screen.blit(cd, (cx - cd.get_width() // 2, status_y))
        elif self._status:
            st = self._font_small.render(self._status, True, self._status_color)
            self.screen.blit(st, (cx - st.get_width() // 2, status_y))

        # Primary button
        btn_y = status_y + 20
        btn_texts = {
            MODE_LOGIN: 'Log In', MODE_REGISTER_EMAIL: 'Send Code',
            MODE_REGISTER_CODE: 'Register', MODE_RESET_EMAIL: 'Send Code',
            MODE_RESET_CODE: 'Reset Password',
        }
        main_rect = self._draw_button(cx, btn_y, btn_texts[self._mode], self._green)
        self._click_rects.append((main_rect, 'submit'))

        # Secondary button (spacing by actual button height)
        aux_y = main_rect.bottom + 10
        aux_texts = {
            MODE_LOGIN: 'Register',
            MODE_REGISTER_EMAIL: 'Back to Login',
            MODE_REGISTER_CODE: 'Resend Code',
            MODE_RESET_EMAIL: 'Back to Login',
            MODE_RESET_CODE: 'Resend Code',
        }
        aux_rect = self._draw_button(cx, aux_y, aux_texts[self._mode],
                                     self._blue, small=True)
        self._click_rects.append((aux_rect, 'aux'))

        # Forgot password link (login mode only)
        forgot_rect = pygame.Rect(0, 0, 1, 1)
        if self._mode == MODE_LOGIN:
            forgot = self._font_hint.render('Forgot Password?', True, self._blue)
            forgot_rect = forgot.get_rect(centerx=cx, top=aux_rect.bottom + 12)
            self.screen.blit(forgot, forgot_rect)
        self._click_rects.append((forgot_rect, 'forgot'))

    def _draw_label_right(self, right_x, y, text):
        """Draw label at specified right-edge position (right-aligned)"""
        label = self._font.render(text, True, self._gray)
        self.screen.blit(label, (right_x - label.get_width(), y + 5))

    def _draw_input(self, x, y, text, w=310, active=False):
        h = 36
        rect = pygame.Rect(x, y, w, h)
        bg = self._inp_active if active else self._inp_bg
        pygame.draw.rect(self.screen, bg, rect, border_radius=4)
        pygame.draw.rect(self.screen, self._blue if active else self._gray,
                         rect, width=2, border_radius=4)

        text_surf = self._font.render(text, True, self._white)
        text_y = y + (h - text_surf.get_height()) // 2
        self.screen.blit(text_surf, (x + 8, text_y))

        if active and self._cursor_timer < 30:
            cx = x + 8 + text_surf.get_width() + 1
            pygame.draw.line(self.screen, self._white,
                             (cx, y + 6), (cx, y + h - 6), 2)
        return rect

    def _draw_button(self, cx, y, text, color, small=False):
        f = self._font_small if small else self._font
        btn_img = f.render(text, True, (0, 0, 0))
        w = btn_img.get_width() + (30 if small else 40)
        h = btn_img.get_height() + (10 if small else 14)
        rect = pygame.Rect(0, 0, w, h)
        rect.centerx = cx
        rect.top = y
        pygame.draw.rect(self.screen, color, rect, border_radius=6)
        self.screen.blit(btn_img, (rect.x + (w - btn_img.get_width()) // 2,
                                   rect.y + (h - btn_img.get_height()) // 2))
        return rect
