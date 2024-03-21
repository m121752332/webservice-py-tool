# -*- coding: utf-8 -*-

###########################################################################
## Python code generated with wxFormBuilder (version 4.1.0-0-g733bf3d)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc

###########################################################################
## Class MainFrame
###########################################################################

class MainFrame ( wx.Frame ):

	def __init__( self, parent ):
		wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = u"WebService測試工具", pos = wx.DefaultPosition, size = wx.Size( 800,550 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

		self.SetSizeHints( wx.Size( 800,550 ), wx.Size( -1,-1 ) )
		self.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_WINDOW ) )

		bSizerMain = wx.BoxSizer( wx.VERTICAL )

		sbSizerTop = wx.StaticBoxSizer( wx.StaticBox( self, wx.ID_ANY, wx.EmptyString ), wx.VERTICAL )

		bSizerName = wx.BoxSizer( wx.HORIZONTAL )

		self.m_static_text_name = wx.StaticText( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"配置名：", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_static_text_name.Wrap( -1 )

		bSizerName.Add( self.m_static_text_name, 0, wx.ALL, 5 )

		self.m_text_ctrl_name = wx.TextCtrl( sbSizerTop.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.Size( 200,-1 ), wx.TE_PROCESS_ENTER )
		bSizerName.Add( self.m_text_ctrl_name, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )


		sbSizerTop.Add( bSizerName, 1, wx.EXPAND, 5 )

		bSizerUrl = wx.BoxSizer( wx.HORIZONTAL )

		self.m_static_text_url = wx.StaticText( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"網址：", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_static_text_url.Wrap( -1 )

		bSizerUrl.Add( self.m_static_text_url, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		m_combo_urlsChoices = []
		self.m_combo_urls = wx.ComboBox( sbSizerTop.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, m_combo_urlsChoices, 0 )
		bSizerUrl.Add( self.m_combo_urls, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		self.m_btn_load = wx.Button( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"讀取", wx.DefaultPosition, wx.DefaultSize, 0 )
		bSizerUrl.Add( self.m_btn_load, 0, wx.ALL, 5 )


		sbSizerTop.Add( bSizerUrl, 1, wx.EXPAND, 5 )

		bSizerMethods = wx.BoxSizer( wx.HORIZONTAL )

		self.m_static_text_methods = wx.StaticText( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"服務：", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_static_text_methods.Wrap( -1 )

		bSizerMethods.Add( self.m_static_text_methods, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		m_combo_methodsChoices = []
		self.m_combo_methods = wx.ComboBox( sbSizerTop.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, m_combo_methodsChoices, wx.CB_DROPDOWN|wx.CB_READONLY )
		self.m_combo_methods.SetForegroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_WINDOWTEXT ) )
		self.m_combo_methods.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_WINDOW ) )
		self.m_combo_methods.SetToolTip( u"選擇服務" )

		bSizerMethods.Add( self.m_combo_methods, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		self.m_btn_start = wx.Button( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"執行請求", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_btn_start.SetToolTip( u"m_btn_start" )
		self.m_btn_start.SetHelpText( u"m_btn_start" )

		bSizerMethods.Add( self.m_btn_start, 0, wx.ALIGN_CENTER_VERTICAL, 5 )

		self.m_btn_clear = wx.Button( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"清空", wx.DefaultPosition, wx.DefaultSize, 0 )
		bSizerMethods.Add( self.m_btn_clear, 0, wx.ALL, 5 )


		sbSizerTop.Add( bSizerMethods, 1, wx.EXPAND, 5 )


		bSizerMain.Add( sbSizerTop, 0, wx.ALL|wx.EXPAND, 5 )

		bSizerBottom = wx.BoxSizer( wx.HORIZONTAL )

		sbSizerLeft = wx.StaticBoxSizer( wx.StaticBox( self, wx.ID_ANY, u"參數（多個用#~#隔開）" ), wx.VERTICAL )

		self.m_text_ctrl_params = wx.TextCtrl( sbSizerLeft.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE|wx.TE_WORDWRAP )
		sbSizerLeft.Add( self.m_text_ctrl_params, 1, wx.ALL|wx.EXPAND, 5 )


		bSizerBottom.Add( sbSizerLeft, 1, wx.ALL|wx.EXPAND, 5 )

		sbSizerRight = wx.StaticBoxSizer( wx.StaticBox( self, wx.ID_ANY, u"回應結果" ), wx.VERTICAL )

		self.m_text_ctrl_result = wx.TextCtrl( sbSizerRight.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_WORDWRAP )
		sbSizerRight.Add( self.m_text_ctrl_result, 1, wx.ALL|wx.EXPAND, 5 )


		bSizerBottom.Add( sbSizerRight, 1, wx.ALL|wx.EXPAND, 5 )


		bSizerMain.Add( bSizerBottom, 1, wx.EXPAND, 5 )


		self.SetSizer( bSizerMain )
		self.Layout()
		self.m_status = self.CreateStatusBar( 1, wx.STB_SIZEGRIP, wx.ID_ANY )
		self.m_status.SetToolTip( u"請選擇網址再選擇服務方法" )


		self.Centre( wx.HORIZONTAL )

		# Connect Events
		self.Bind( wx.EVT_CLOSE, self.OnMenuClickEventExit )
		self.m_text_ctrl_name.Bind( wx.EVT_TEXT, self.OnTextCtrlNameText )
		self.m_text_ctrl_name.Bind( wx.EVT_TEXT_ENTER, self.OnTextCtrlNameTextEnter )
		self.m_text_ctrl_name.Bind( wx.EVT_TEXT_MAXLEN, self.OnTextCtrlNameMaxLen )
		self.m_combo_urls.Bind( wx.EVT_COMBOBOX, self.OnComboBoxUrlsSelect )
		self.m_combo_urls.Bind( wx.EVT_TEXT, self.OnComboBoxUrlsText )
		self.m_combo_urls.Bind( wx.EVT_TEXT_ENTER, self.OnComboBoxUrlsEnter )
		self.m_btn_load.Bind( wx.EVT_BUTTON, self.OnClickEventLoad )
		self.m_combo_methods.Bind( wx.EVT_COMBOBOX, self.OnComboBoxMethodSelect )
		self.m_combo_methods.Bind( wx.EVT_TEXT, self.OnComboBoxMethodText )
		self.m_combo_methods.Bind( wx.EVT_TEXT_ENTER, self.OnComboBoxMethodTextEnter )
		self.m_btn_start.Bind( wx.EVT_BUTTON, self.OnClickEventStart )
		self.m_btn_clear.Bind( wx.EVT_BUTTON, self.OnClickEventClear )

	def __del__( self ):
		pass


	# Virtual event handlers, override them in your derived class
	def OnMenuClickEventExit( self, event ):
		event.Skip()

	def OnTextCtrlNameText( self, event ):
		event.Skip()

	def OnTextCtrlNameTextEnter( self, event ):
		event.Skip()

	def OnTextCtrlNameMaxLen( self, event ):
		event.Skip()

	def OnComboBoxUrlsSelect( self, event ):
		event.Skip()

	def OnComboBoxUrlsText( self, event ):
		event.Skip()

	def OnComboBoxUrlsEnter( self, event ):
		event.Skip()

	def OnClickEventLoad( self, event ):
		event.Skip()

	def OnComboBoxMethodSelect( self, event ):
		event.Skip()

	def OnComboBoxMethodText( self, event ):
		event.Skip()

	def OnComboBoxMethodTextEnter( self, event ):
		event.Skip()

	def OnClickEventStart( self, event ):
		event.Skip()

	def OnClickEventClear( self, event ):
		event.Skip()


