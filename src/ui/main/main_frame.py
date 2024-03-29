# -*- coding: utf-8 -*-

###########################################################################
## Python code generated with wxFormBuilder (version 4.1.0-0-g733bf3d)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc

ID_ESC = 1000
ID_NEW = 1001
ID_DEL = 1002
ID_LOAD = 1003
ID_RUN = 1004
ID_CLEAR = 1005
ID_ABOUT = 1006

###########################################################################
## Class MainFrame
###########################################################################

class MainFrame ( wx.Frame ):

	def __init__( self, parent ):
		wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = u"WebService測試工具", pos = wx.DefaultPosition, size = wx.Size( 800,550 ), style = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )

		self.SetSizeHints( wx.Size( 800,550 ), wx.Size( -1,-1 ) )
		self.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_WINDOW ) )

		self.m_menubar = wx.MenuBar( 0|wx.BORDER_THEME )
		self.m_file = wx.Menu()
		self.m_item_exit = wx.MenuItem( self.m_file, ID_ESC, u"離開"+ u"\t" + u"esc", u"按下Esc離開", wx.ITEM_NORMAL )
		self.m_file.Append( self.m_item_exit )

		self.m_menubar.Append( self.m_file, u"檔案" )

		self.m_run = wx.Menu()
		self.m_item_new = wx.MenuItem( self.m_run, ID_NEW, u"新增配置"+ u"\t" + u"f1", u"新增連線配置[F1]", wx.ITEM_NORMAL )
		self.m_run.Append( self.m_item_new )

		self.m_item_del = wx.MenuItem( self.m_run, ID_DEL, u"刪除配置"+ u"\t" + u"f2", u"刪除連線配置[F2]", wx.ITEM_NORMAL )
		self.m_run.Append( self.m_item_del )

		self.m_item_load = wx.MenuItem( self.m_run, ID_LOAD, u"讀取操作"+ u"\t" + u"f3", u"讀取服務網址的服務[F3]", wx.ITEM_NORMAL )
		self.m_run.Append( self.m_item_load )

		self.m_run.AppendSeparator()

		self.m_item_run = wx.MenuItem( self.m_run, ID_RUN, u"執行請求"+ u"\t" + u"f5", u"執行貼上的請求內容[F5]", wx.ITEM_NORMAL )
		self.m_run.Append( self.m_item_run )

		self.m_item_clear = wx.MenuItem( self.m_run, ID_CLEAR, u"清空服務格內容"+ u"\t" + u"f6", u"清除服務的內容，如操作服務+請求+回應[F6]", wx.ITEM_NORMAL )
		self.m_run.Append( self.m_item_clear )

		self.m_menubar.Append( self.m_run, u"執行" )

		self.m_help = wx.Menu()
		self.m_item_about = wx.MenuItem( self.m_help, ID_ABOUT, u"About"+ u"\t" + u"f8", u"作者資訊", wx.ITEM_NORMAL )
		self.m_help.Append( self.m_item_about )

		self.m_menubar.Append( self.m_help, u"幫助" )

		self.SetMenuBar( self.m_menubar )

		bSizerMain = wx.BoxSizer( wx.VERTICAL )

		sbSizerTop = wx.StaticBoxSizer( wx.StaticBox( self, wx.ID_ANY, wx.EmptyString ), wx.VERTICAL )

		bSizerName = wx.BoxSizer( wx.HORIZONTAL )

		self.m_static_text_name = wx.StaticText( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"配  置  名：", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_static_text_name.Wrap( -1 )

		bSizerName.Add( self.m_static_text_name, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		self.m_text_ctrl_name = wx.TextCtrl( sbSizerTop.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.Size( 200,-1 ), wx.TE_PROCESS_ENTER )
		bSizerName.Add( self.m_text_ctrl_name, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )


		bSizerName.Add( ( 0, 0), 1, wx.EXPAND, 5 )

		self.m_btn_append_connect = wx.Button( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"新增配置", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_btn_append_connect.SetToolTip( u"新增配置[m_btn_append_connect]" )

		bSizerName.Add( self.m_btn_append_connect, 0, wx.ALL, 5 )

		self.m_btn_delete_connect = wx.Button( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"刪除配置", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_btn_delete_connect.SetToolTip( u"刪除配置[m_btn_delete_file]" )

		bSizerName.Add( self.m_btn_delete_connect, 0, wx.ALL, 5 )


		sbSizerTop.Add( bSizerName, 1, wx.EXPAND, 5 )

		bSizerUrl = wx.BoxSizer( wx.HORIZONTAL )

		self.m_static_text_url = wx.StaticText( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"服務網址：", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_static_text_url.Wrap( -1 )

		bSizerUrl.Add( self.m_static_text_url, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		m_combo_urlsChoices = []
		self.m_combo_urls = wx.ComboBox( sbSizerTop.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, m_combo_urlsChoices, wx.CB_DROPDOWN )
		bSizerUrl.Add( self.m_combo_urls, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		self.m_btn_load = wx.Button( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"讀取", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_btn_load.SetToolTip( u"讀取[m_btn_load]" )

		bSizerUrl.Add( self.m_btn_load, 0, wx.ALL, 5 )


		sbSizerTop.Add( bSizerUrl, 1, wx.EXPAND, 5 )

		bSizerHelp = wx.BoxSizer( wx.HORIZONTAL )

		bSizerHelp.SetMinSize( wx.Size( 0,0 ) )
		self.m_static_text_dummy = wx.StaticText( sbSizerTop.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.Size( 80,-1 ), 0 )
		self.m_static_text_dummy.Wrap( -1 )

		bSizerHelp.Add( self.m_static_text_dummy, 0, wx.ALL, 1 )

		self.m_static_text_tooltip = wx.StaticText( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"* 結尾請記得加上 ?WSDL 當後綴", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_static_text_tooltip.SetLabelMarkup( u"* 結尾請記得加上 ?WSDL 當後綴" )
		self.m_static_text_tooltip.Wrap( -1 )

		self.m_static_text_tooltip.SetForegroundColour( wx.Colour( 0, 0, 128 ) )
		self.m_static_text_tooltip.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_HIGHLIGHTTEXT ) )

		bSizerHelp.Add( self.m_static_text_tooltip, 0, wx.ALL, 1 )


		sbSizerTop.Add( bSizerHelp, 1, wx.EXPAND, 0 )

		bSizerMethods = wx.BoxSizer( wx.HORIZONTAL )

		self.m_static_text_methods = wx.StaticText( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"操作服務：", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_static_text_methods.Wrap( -1 )

		bSizerMethods.Add( self.m_static_text_methods, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		m_combo_methodsChoices = []
		self.m_combo_methods = wx.ComboBox( sbSizerTop.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, m_combo_methodsChoices, wx.CB_DROPDOWN|wx.CB_READONLY )
		self.m_combo_methods.SetForegroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_WINDOWTEXT ) )
		self.m_combo_methods.SetBackgroundColour( wx.SystemSettings.GetColour( wx.SYS_COLOUR_WINDOW ) )
		self.m_combo_methods.SetToolTip( u"選擇服務" )

		bSizerMethods.Add( self.m_combo_methods, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5 )

		self.m_btn_start = wx.Button( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"執行請求", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_btn_start.SetToolTip( u"執行請求[m_btn_start]" )
		self.m_btn_start.SetHelpText( u"m_btn_start" )

		bSizerMethods.Add( self.m_btn_start, 0, wx.ALIGN_CENTER_VERTICAL, 5 )

		self.m_btn_clear = wx.Button( sbSizerTop.GetStaticBox(), wx.ID_ANY, u"清空服務", wx.DefaultPosition, wx.DefaultSize, 0 )
		self.m_btn_clear.SetToolTip( u"清空[m_btn_clear]" )

		bSizerMethods.Add( self.m_btn_clear, 0, wx.ALL, 5 )


		sbSizerTop.Add( bSizerMethods, 1, wx.EXPAND, 5 )


		bSizerMain.Add( sbSizerTop, 0, wx.ALL|wx.EXPAND, 5 )

		self.m_splitter_method = wx.SplitterWindow( self, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.SP_3D )
		self.m_splitter_method.Bind( wx.EVT_IDLE, self.m_splitter_methodOnIdle )
		self.m_splitter_method.SetMinimumPaneSize( 50 )

		self.m_panel_left = wx.Panel( self.m_splitter_method, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
		sbSizerLeft = wx.StaticBoxSizer( wx.StaticBox( self.m_panel_left, wx.ID_ANY, u"請求參數（多個用#~#隔開）" ), wx.VERTICAL )

		self.m_text_ctrl_params = wx.TextCtrl( sbSizerLeft.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE|wx.TE_WORDWRAP )
		sbSizerLeft.Add( self.m_text_ctrl_params, 1, wx.ALL|wx.EXPAND, 5 )


		self.m_panel_left.SetSizer( sbSizerLeft )
		self.m_panel_left.Layout()
		sbSizerLeft.Fit( self.m_panel_left )
		self.m_panel_right = wx.Panel( self.m_splitter_method, wx.ID_ANY, wx.DefaultPosition, wx.DefaultSize, wx.TAB_TRAVERSAL )
		sbSizerRight = wx.StaticBoxSizer( wx.StaticBox( self.m_panel_right, wx.ID_ANY, u"回應結果" ), wx.VERTICAL )

		self.m_text_ctrl_result = wx.TextCtrl( sbSizerRight.GetStaticBox(), wx.ID_ANY, wx.EmptyString, wx.DefaultPosition, wx.DefaultSize, wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_WORDWRAP )
		sbSizerRight.Add( self.m_text_ctrl_result, 1, wx.ALL|wx.EXPAND, 5 )


		self.m_panel_right.SetSizer( sbSizerRight )
		self.m_panel_right.Layout()
		sbSizerRight.Fit( self.m_panel_right )
		self.m_splitter_method.SplitVertically( self.m_panel_left, self.m_panel_right, 324 )
		bSizerMain.Add( self.m_splitter_method, 1, wx.EXPAND|wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 5 )


		self.SetSizer( bSizerMain )
		self.Layout()
		self.m_status = self.CreateStatusBar( 1, wx.STB_SIZEGRIP, wx.ID_ANY )
		self.m_status.SetToolTip( u"請選擇網址再選擇服務方法" )
		self.m_status.SetHelpText( u"請選擇網址再選擇服務方法" )


		self.Centre( wx.HORIZONTAL )

		# Connect Events
		self.Bind( wx.EVT_CLOSE, self.OnMenuClickEventExit )
		self.Bind( wx.EVT_MENU, self.OnMenuClickEventExit, id = self.m_item_exit.GetId() )
		self.Bind( wx.EVT_MENU, self.OnClickEventDel, id = self.m_item_del.GetId() )
		self.Bind( wx.EVT_MENU, self.OnClickEventLoad, id = self.m_item_load.GetId() )
		self.Bind( wx.EVT_MENU, self.OnClickEventStart, id = self.m_item_run.GetId() )
		self.Bind( wx.EVT_MENU, self.OnClickEventClear, id = self.m_item_clear.GetId() )
		self.Bind( wx.EVT_MENU, self.OnMenuClickEventAbout, id = self.m_item_about.GetId() )
		self.m_text_ctrl_name.Bind( wx.EVT_KILL_FOCUS, self.OnTextCtrlNameKillFocus )
		self.m_text_ctrl_name.Bind( wx.EVT_SET_FOCUS, self.OnTextCtrlNameSetFocus )
		self.m_text_ctrl_name.Bind( wx.EVT_TEXT, self.OnTextCtrlNameText )
		self.m_text_ctrl_name.Bind( wx.EVT_TEXT_ENTER, self.OnTextCtrlNameTextEnter )
		self.m_text_ctrl_name.Bind( wx.EVT_TEXT_MAXLEN, self.OnTextCtrlNameMaxLen )
		self.m_btn_append_connect.Bind( wx.EVT_BUTTON, self.OnClickEventAdd )
		self.m_btn_delete_connect.Bind( wx.EVT_BUTTON, self.OnClickEventDel )
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


	def OnClickEventDel( self, event ):
		event.Skip()

	def OnClickEventLoad( self, event ):
		event.Skip()

	def OnClickEventStart( self, event ):
		event.Skip()

	def OnClickEventClear( self, event ):
		event.Skip()

	def OnMenuClickEventAbout( self, event ):
		event.Skip()

	def OnTextCtrlNameKillFocus( self, event ):
		event.Skip()

	def OnTextCtrlNameSetFocus( self, event ):
		event.Skip()

	def OnTextCtrlNameText( self, event ):
		event.Skip()

	def OnTextCtrlNameTextEnter( self, event ):
		event.Skip()

	def OnTextCtrlNameMaxLen( self, event ):
		event.Skip()

	def OnClickEventAdd( self, event ):
		event.Skip()


	def OnComboBoxUrlsSelect( self, event ):
		event.Skip()

	def OnComboBoxUrlsText( self, event ):
		event.Skip()

	def OnComboBoxUrlsEnter( self, event ):
		event.Skip()


	def OnComboBoxMethodSelect( self, event ):
		event.Skip()

	def OnComboBoxMethodText( self, event ):
		event.Skip()

	def OnComboBoxMethodTextEnter( self, event ):
		event.Skip()



	def m_splitter_methodOnIdle( self, event ):
		self.m_splitter_method.SetSashPosition( 324 )
		self.m_splitter_method.Unbind( wx.EVT_IDLE )


